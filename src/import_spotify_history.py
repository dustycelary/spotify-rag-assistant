#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import re
import socket
import time
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import dotenv

dotenv.load_dotenv()

# Fallback DB_HOST to localhost if running outside Docker
db_host = os.environ.get("DB_HOST", "localhost")
try:
    socket.gethostbyname(db_host)
except socket.gaierror:
    os.environ["DB_HOST"] = "localhost"

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db import SessionLocal, engine, init_db
from src.import_enrichment import run_post_import_enrichment
from src.models.artist import Artist
from src.models.played_history import PlayedHistory
from src.models.track import Track, track_artists

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("import_spotify_history")


class NormalizedPlay:
    track_uri: str
    title: str
    artist_name: str | None
    album_name: str | None
    played_at: datetime
    playback_ms: int


@dataclass
class HistoryParseResult:
    total_records_read: int
    tracks_by_uri: dict[str, dict]
    artists_by_uri: dict[str, dict]
    track_artist_pairs: set[tuple[str, str]]
    plays: list[dict]


def normalise_history_record(item: Mapping[str, object]) -> NormalizedPlay:
    """Normalises Spotify history record into a normalized play object."""

    track_uri = item.get("spotify_track_uri")
    track_name = item.get("master_metadata_track_name")
    artist_name = item.get("master_metadata_album_artist_name")
    album_name = item.get("master_metadata_album_album_name")

    if not track_uri:
        return None

    ts_val = item.get("ts")
    ms_played = item.get("ms_played")
    played_at = parse_timestamp(ts_val)
    if not played_at or not ms_played:
        return None
    time_played = int(ms_played)

    return NormalizedPlay(
        track_uri=track_uri,
        title=track_name or "Unknown Title",
        artist_name=artist_name,
        album_name=album_name,
        played_at=played_at,
        playback_ms=time_played,
    )


def clean_slug(text: str) -> str:
    """Generates a clean string slug for fallback URIs."""
    return re.sub(r"[^a-z0-9]", "_", text.lower()).strip("_")


def generate_local_uri(entity_type: str, *components: str) -> str:
    """Generates a canonical versioned local URI.

    Steps:
    1. Apply Unicode NFKC normalization to identity components.
    2. Strip whitespace and case-fold for canonical identity.
    3. Build a readable Unicode-safe slug.
    4. Use `track` or `artist` if the readable part becomes empty.
    5. Append 12 hexadecimal characters from SHA-256 of the full canonical identity.
    6. Use versioned prefixes: spotify:<entity_type>:local:v1:<slug>:<hash_12>
    """
    canonical_parts = [
        unicodedata.normalize("NFKC", c).strip().casefold()
        for c in components
        if c is not None
    ]
    canonical_identity = "::".join(canonical_parts)

    slug = re.sub(r"[^\w]+", "-", canonical_identity, flags=re.UNICODE).strip("-")

    if not slug:
        slug = entity_type

    identity_hash = hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()[:12]

    return f"spotify:{entity_type}:local:v1:{slug}:{identity_hash}"


def parse_timestamp(value: object) -> datetime | None:
    """Parses various timestamp formats into UTC datetime object.

    - Convert Z, positive offsets, and negative offsets to
      timezone.utc using .astimezone(timezone.utc).
    - Interpret YYYY-MM-DD HH:MM as UTC.
    - Return None for blank, non-string, malformed, or impossible values.
    """
    if not isinstance(value, str) or not value:
        return None

    val = value.strip()

    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError) as e:
        logger.debug("Failed to parse timestamp %r: %s", value, e)
        return None


def truncate_all_tables(bind=engine):
    """Truncates all application database tables with CASCADE."""
    logger.info("Truncating application database tables...")
    with bind.begin() as conn:
        conn.execute(
            text("""
                TRUNCATE TABLE
            played_history,
            embeddings,
            audio_features,
            track_artists,
            artists,
            tracks
                RESTART IDENTITY CASCADE;
            """)
        )
    logger.info("Re-initializing database schema & views...")
    init_db(bind)


def discover_json_files(target_path: Path) -> list[Path]:
    """Finds all Spotify streaming history JSON files in target directory or file."""
    if target_path.is_file():
        return [target_path]
    if target_path.is_dir():
        files = list(target_path.glob("*.json"))
        return sorted(files)
    return []


def parse_spotify_history_files(json_files: list[Path]) -> HistoryParseResult:
    """Parses Spotify history JSON files and extracts structured records."""
    result = HistoryParseResult(
        total_records_read=0,
        tracks_by_uri={},
        artists_by_uri={},
        track_artist_pairs=set(),
        plays=[],
    )

    for filepath in json_files:
        logger.info("Parsing history file: %s", filepath.name)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to read JSON file %s: %s", filepath, e)
            continue

        if not isinstance(data, list):
            continue

        for item in data:
            result.total_records_read += 1
            norm = normalise_history_record(item)

            # Track entry
            if norm.track_uri not in result.tracks_by_uri:
                result.tracks_by_uri[norm.track_uri] = {
                    "uri": norm.track_uri,
                    "title": norm.track_name or "Unknown Title",
                    "album_name": norm.album_name,
                    "duration_ms": None,
                }

            # Artist & Track-Artist relationship
            if norm.artist_name:
                artist_uri = f"spotify:artist:local:{clean_slug(norm.artist_name)}"
                if artist_uri not in result.artists_by_uri:
                    result.artists_by_uri[artist_uri] = {
                        "uri": artist_uri,
                        "name": norm.artist_name,
                    }
                result.track_artist_pairs.add((norm.track_uri, artist_uri))

            # Played History entry
            result.plays.append(
                {
                    "track_uri": norm.track_uri,
                    "played_at": norm.played_at,
                }
            )

    return result


def bulk_insert_records(
    parsed: HistoryParseResult, session_factory=SessionLocal, chunk_size=5000
):
    """Inserts records in chunks using PostgreSQL bulk upsert."""
    t0 = time.time()
    with session_factory() as session:
        # 1. Tracks
        track_values = list(parsed.tracks_by_uri.values())
        if track_values:  # prevents empty list
            logger.info("Inserting %d unique tracks...", len(track_values))
            for i in range(0, len(track_values), chunk_size):
                chunk = track_values[i : i + chunk_size]
                stmt = (
                    pg_insert(Track)
                    .values(chunk)
                    .on_conflict_do_nothing(index_elements=["uri"])
                )
                session.execute(stmt)

        # 2. Artists
        artist_values = list(parsed.artists_by_uri.values())
        logger.info("Inserting %d unique artists...", len(artist_values))
        if artist_values:  # prevents empty list:
            for i in range(0, len(artist_values), chunk_size):
                chunk = artist_values[i : i + chunk_size]
                stmt = (
                    pg_insert(Artist)
                    .values(chunk)
                    .on_conflict_do_nothing(index_elements=["uri"])
                )
                session.execute(stmt)

        if parsed.track_artist_pairs:
            logger.info(
                "Inserting %d track-artist relationships...",
                len(parsed.track_artist_pairs),
            )
            ta_values = [
                {"track_uri": tu, "artist_uri": au}
                for tu, au in parsed.track_artist_pairs
            ]
            for i in range(0, len(ta_values), chunk_size):
                chunk = ta_values[i : i + chunk_size]
                stmt = (
                    pg_insert(track_artists)
                    .values(chunk)
                    .on_conflict_do_nothing(index_elements=["track_uri", "artist_uri"])
                )
                session.execute(stmt)

        # 4. Bulk Insert Listening History (Plays)
        if parsed.plays:
            logger.info("Inserting %d listening history records...", len(parsed.plays))
            for i in range(0, len(parsed.plays), chunk_size):
                chunk = parsed.plays[i : i + chunk_size]
                stmt = (
                    pg_insert(PlayedHistory)
                    .values(chunk)
                    .on_conflict_do_nothing(constraint="unique_history_play")
                )
                session.execute(stmt)

        session.commit()

    t1 = time.time()
    logger.info("Bulk database insert completed in %.2f seconds.", t1 - t0)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Import Spotify Extended Streaming History JSON files into "
            "PostgreSQL database."
        )
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to Spotify history JSON directory or file.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe/truncate all existing database tables before importing.",
    )
    args = parser.parse_args()

    # Determine input directory
    if args.path:
        target_path = Path(args.path).resolve()
    else:
        search_dirs = [
            "spotify_data",
            "data",
        ]
        target_path = next(
            (d for d in search_dirs if d.exists() and len(list(d.glob("*.json"))) > 0),
            None,
        )

    if not target_path or not target_path.exists():
        print("\n=======================================================")
        print("📥 SPOTIFY STREAMING HISTORY IMPORTER")
        print("=======================================================")
        print("No Spotify history JSON files specified or found.")
        print("\nHow to use:")
        print(" 1. Download your 'Extended Streaming History' from Spotify:")
        print("    https://www.spotify.com/account/privacy/")
        print(
            " 2. Place your JSON files (endsong_*.json / Audio_*.json) in "
            "'src/spotify_data/'"
        )
        print(" 3. Run this script:")
        print("    python src/import_spotify_history.py --path src/spotify_data/")
        print("    python src/import_spotify_history.py --reset")
        print("=======================================================\n")
        return

    json_files = discover_json_files(target_path)
    if not json_files:
        logger.error("No .json files found in %s", target_path)
        return

    print("\n=======================================================")
    print("🎵 SPOTIFY STREAMING HISTORY IMPORTER")
    print("=======================================================")
    print(f" Source Directory: {target_path}")
    print(f" Files Found:      {len(json_files)}")
    if args.reset:
        print(" Reset Database:   YES (all tables will be wiped)")
    else:
        print(" Reset Database:   NO (new records will be appended)")
    print("=======================================================\n")

    # 1. Truncate tables if --reset
    if args.reset:
        truncate_all_tables()
    else:
        init_db(engine)

    # 2. Parse JSON history files
    total_records, tracks_dict, artists_dict, track_artists_set, plays_list = (
        parse_spotify_history_files(json_files)
    )

    # 3. Bulk insert to DB
    bulk_insert_records(tracks_dict, artists_dict, track_artists_set, plays_list)
    enrichment_stats = run_post_import_enrichment(logger)

    # 4. Verification & Summary Report
    with SessionLocal() as session:
        db_tracks = session.query(Track).count()
        db_artists = session.query(Artist).count()
        db_plays = session.query(PlayedHistory).count()

    print("\n=======================================================")
    print("🎉 IMPORT COMPLETE!")
    print("=======================================================")
    print(f" Total Records Read:  {total_records:,}")
    print(f" Tracks in DB:        {db_tracks:,}")
    print(f" Artists in DB:       {db_artists:,}")
    print(f" Plays in DB:         {db_plays:,}")
    print(f" Feature Candidates:  {enrichment_stats['feature_candidates']:,}")
    print(f" Features Upserted:   {enrichment_stats['features_upserted']:,}")
    print(f" Embedding Candidates:{enrichment_stats['embedding_candidates']:,}")
    print(f" Embeddings Upserted: {enrichment_stats['embeddings_upserted']:,}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
