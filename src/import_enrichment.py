import logging
import os
from collections.abc import Sequence
from typing import TypeVar

import spotipy
from sentence_transformers import SentenceTransformer
from spotipy.oauth2 import SpotifyClientCredentials
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db import SessionLocal
from src.models.audio_features import AudioFeatures
from src.models.embedding import Embedding

T = TypeVar("T")


def _chunks(values: Sequence[T], size: int) -> list[list[T]]:
    return [list(values[i : i + size]) for i in range(0, len(values), size)]


def _to_track_id(track_uri: str) -> str | None:
    prefix = "spotify:track:"
    if not track_uri or not track_uri.startswith(prefix):
        return None
    track_id = track_uri[len(prefix) :]
    if not track_id or track_id.startswith("local:"):
        return None
    return track_id


def get_spotify_client(logger: logging.Logger) -> spotipy.Spotify | None:
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning(
            "Spotify client credentials missing; skipping audio feature enrichment."
        )
        return None

    try:
        return spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
        )
    except Exception as e:
        logger.warning("Failed to initialize Spotify API client: %s", e)
        return None


def enrich_audio_features(
    logger: logging.Logger, batch_size: int = 100
) -> dict[str, int]:
    with SessionLocal() as session:
        missing_feature_uris = (
            session.execute(
                text(
                    """
                SELECT t.uri
                FROM tracks t
                LEFT JOIN audio_features af ON af.track_uri = t.uri
                WHERE af.track_uri IS NULL
                """
                )
            )
            .scalars()
            .all()
        )

    if not missing_feature_uris:
        return {"feature_candidates": 0, "features_upserted": 0}

    sp = get_spotify_client(logger)
    features_upserted = 0

    with SessionLocal() as session:
        for uris_chunk in _chunks(list(missing_feature_uris), batch_size):
            rows = []
            spotify_ids = []
            uri_to_chunk_map = {}

            for uri in uris_chunk:
                track_id = _to_track_id(uri)
                if track_id:
                    spotify_ids.append(track_id)
                    uri_to_chunk_map[track_id] = uri

            api_features_map = {}
            if sp and spotify_ids:
                try:
                    fetched_features = sp.audio_features(spotify_ids)
                    for feat in fetched_features or []:
                        if feat and feat.get("id"):
                            api_features_map[feat["id"]] = feat
                except Exception as e:
                    logger.warning("Spotify audio_features API fetch failed: %s", e)

            for uri in uris_chunk:
                track_id = _to_track_id(uri)
                feat = api_features_map.get(track_id) if track_id else None
                if feat:
                    rows.append(
                        {
                            "track_uri": uri,
                            "valence": feat.get("valence"),
                            "energy": feat.get("energy"),
                            "danceability": feat.get("danceability"),
                            "tempo": feat.get("tempo"),
                            "acousticness": feat.get("acousticness"),
                            "instrumentalness": feat.get("instrumentalness"),
                            "liveness": feat.get("liveness"),
                            "loudness": feat.get("loudness"),
                            "speechiness": feat.get("speechiness"),
                        }
                    )
            if not rows:
                continue

            insert_stmt = pg_insert(AudioFeatures).values(rows)
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["track_uri"],
                set_={
                    "valence": insert_stmt.excluded.valence,
                    "energy": insert_stmt.excluded.energy,
                    "danceability": insert_stmt.excluded.danceability,
                    "tempo": insert_stmt.excluded.tempo,
                    "acousticness": insert_stmt.excluded.acousticness,
                    "instrumentalness": insert_stmt.excluded.instrumentalness,
                    "liveness": insert_stmt.excluded.liveness,
                    "loudness": insert_stmt.excluded.loudness,
                    "speechiness": insert_stmt.excluded.speechiness,
                },
            )
            session.execute(stmt)
            session.commit()
            features_upserted += len(rows)

    return {
        "feature_candidates": len(missing_feature_uris),
        "features_upserted": features_upserted,
    }


def _embedding_text(row: dict) -> str:
    parts = [
        f"track {row.get('title') or 'unknown title'}",
        f"by {row.get('artist_names') or 'unknown artist'}",
    ]
    if row.get("album_name"):
        parts.append(f"album {row['album_name']}")
    if row.get("tempo") is not None:
        parts.append(f"tempo {round(float(row['tempo']), 1)} bpm")
    if row.get("energy") is not None:
        parts.append(f"energy {round(float(row['energy']), 3)}")
    if row.get("danceability") is not None:
        parts.append(f"danceability {round(float(row['danceability']), 3)}")
    if row.get("valence") is not None:
        parts.append(f"valence {round(float(row['valence']), 3)}")
    return ". ".join(parts)


def enrich_embeddings(
    logger: logging.Logger,
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 256,
) -> dict[str, int]:
    with SessionLocal() as session:
        rows = (
            session.execute(
                text(
                    """
                SELECT
                    t.uri AS track_uri,
                    t.title,
                    t.album_name,
                    COALESCE(
                        string_agg(DISTINCT a.name, ', '),
                        'Unknown Artist'
                    ) AS artist_names,
                    af.tempo,
                    af.energy,
                    af.danceability,
                    af.valence
                FROM tracks t
                LEFT JOIN track_artists ta ON ta.track_uri = t.uri
                LEFT JOIN artists a ON a.uri = ta.artist_uri
                LEFT JOIN audio_features af ON af.track_uri = t.uri
                LEFT JOIN embeddings e ON e.track_uri = t.uri
                WHERE e.track_uri IS NULL
                GROUP BY
                    t.uri, t.title, t.album_name, af.tempo, af.energy,
                    af.danceability, af.valence
                """
                )
            )
            .mappings()
            .all()
        )

    if not rows:
        return {"embedding_candidates": 0, "embeddings_upserted": 0}

    try:
        model = SentenceTransformer(model_name)
    except Exception as e:
        logger.warning("Failed to initialize embedding model '%s': %s", model_name, e)
        return {"embedding_candidates": len(rows), "embeddings_upserted": 0}

    embeddings_upserted = 0
    with SessionLocal() as session:
        for rows_chunk in _chunks(list(rows), batch_size):
            texts = [_embedding_text(row) for row in rows_chunk]
            vectors = model.encode(texts).tolist()
            insert_rows = [
                {"track_uri": row["track_uri"], "embedding": vec}
                for row, vec in zip(rows_chunk, vectors, strict=True)
            ]

            insert_stmt = pg_insert(Embedding).values(insert_rows)
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["track_uri"],
                set_={"embedding": insert_stmt.excluded.embedding},
            )
            session.execute(stmt)
            session.commit()
            embeddings_upserted += len(insert_rows)

    return {
        "embedding_candidates": len(rows),
        "embeddings_upserted": embeddings_upserted,
    }


def run_post_import_enrichment(logger: logging.Logger) -> dict[str, int]:
    audio_stats = enrich_audio_features(logger=logger)
    embedding_stats = enrich_embeddings(logger=logger)
    stats = {**audio_stats, **embedding_stats}
    logger.info(
        "Enrichment complete: %s feature candidates, %s features upserted, "
        "%s embedding candidates, %s embeddings upserted.",
        stats["feature_candidates"],
        stats["features_upserted"],
        stats["embedding_candidates"],
        stats["embeddings_upserted"],
    )
    return stats
