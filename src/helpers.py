from typing import Any

from src.db import SessionLocal


def remove_keys_recursive(obj: Any, keys_to_remove: set[str]) -> Any:
    """Recursively removes specified keys from dictionaries or lists of dictionaries."""
    if isinstance(obj, dict):
        return {
            k: remove_keys_recursive(v, keys_to_remove)
            for k, v in obj.items()
            if k not in keys_to_remove
        }
    elif isinstance(obj, list):
        return [remove_keys_recursive(item, keys_to_remove) for item in obj]
    return obj


def sync_spotify_to_db(sp: Any) -> dict[str, int]:
    """Fetches the user's recently played tracks from Spotify and saves new ones to DB.

    Returns:
        dict[str, int]: Counts of new tracks and plays inserted.
    """
    import logging
    from datetime import datetime

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from src.models.artist import Artist
    from src.models.played_history import PlayedHistory
    from src.models.track import Track, track_artists

    logger = logging.getLogger(__name__)
    if not sp:
        return {"tracks_added": 0, "plays_inserted": 0}

    logger.info("Syncing Spotify recently played tracks to database...")
    try:
        # Fetch the max possible limit from Spotify (50)
        recent_played = sp.current_user_recently_played(limit=50)
        items = recent_played.get("items", [])
    except Exception as e:
        logger.error("Failed to fetch recently played tracks from Spotify: %s", e)
        return {"tracks_added": 0, "plays_inserted": 0}

    tracks_added = 0
    plays_inserted = 0

    try:
        with SessionLocal() as session:
            for item in items:
                track_data = item.get("track", {})
                track_uri = track_data.get("uri")
                track_name = track_data.get("name")
                album_data = track_data.get("album", {})
                album_name = album_data.get("name")
                album_uri = album_data.get("uri")
                played_at_str = item.get("played_at")

                if not track_uri or not played_at_str:
                    continue

                try:
                    played_at = datetime.fromisoformat(
                        played_at_str.replace("Z", "+00:00")
                    )
                except Exception:
                    continue

                # 1. Insert Track metadata
                track_stmt = (
                    pg_insert(Track)
                    .values(
                        uri=track_uri,
                        title=track_name or "Unknown Title",
                        album_name=album_name,
                        album_uri=album_uri,
                        popularity=track_data.get("popularity"),
                        duration_ms=track_data.get("duration_ms"),
                    )
                    .on_conflict_do_nothing(index_elements=["uri"])
                )

                res_track = session.execute(track_stmt)
                if res_track.rowcount > 0:
                    tracks_added += 1

                # 1b. Insert Artist records and Track-Artist relations
                for artist_info in track_data.get("artists", []):
                    artist_uri = artist_info.get("uri")
                    artist_name = artist_info.get("name")
                    if artist_uri and artist_name:
                        artist_stmt = (
                            pg_insert(Artist)
                            .values(
                                uri=artist_uri,
                                name=artist_name,
                            )
                            .on_conflict_do_nothing(index_elements=["uri"])
                        )
                        session.execute(artist_stmt)

                        ta_stmt = (
                            pg_insert(track_artists)
                            .values(
                                track_uri=track_uri,
                                artist_uri=artist_uri,
                            )
                            .on_conflict_do_nothing()
                        )
                        session.execute(ta_stmt)

                # 2. Insert PlayedHistory event
                context = item.get("context") or {}
                play_stmt = (
                    pg_insert(PlayedHistory)
                    .values(
                        track_uri=track_uri,
                        played_at=played_at,
                        context_type=context.get("type"),
                        context_uri=context.get("uri"),
                    )
                    .on_conflict_do_nothing(constraint="unique_history_play")
                )

                res_play = session.execute(play_stmt)
                if res_play.rowcount > 0:
                    plays_inserted += 1

            session.commit()
        logger.info(
            "Sync complete: %d new tracks added, %d new play events saved.",
            tracks_added,
            plays_inserted,
        )
    except Exception as e:
        logger.error("Failed to write synced tracks to DB: %s", e)

    return {"tracks_added": tracks_added, "plays_inserted": plays_inserted}


def sync_artist_genres(sp: Any) -> int:
    """Fetches and updates genre + popularity data for artists missing genres.

    Handles two URI formats:
    - Standard Spotify URIs (spotify:artist:<id>): batch lookup via sp.artists()
    - Data-export URIs (spotify:artist:local:<slug>): individual search by name

    Returns:
        int: Number of artists updated with genre data.
    """
    import logging
    import time

    from src.models.artist import Artist

    logger = logging.getLogger(__name__)

    if not sp:
        return 0

    logger.info("Syncing artist genres from Spotify API...")
    updated_count = 0

    try:
        with SessionLocal() as session:
            artists_missing_genres = (
                session.query(Artist)
                .filter(Artist.genres.is_(None))
                .all()
            )

            if not artists_missing_genres:
                logger.info("All artists already have genre data.")
                return 0

            # Split into batch-fetchable (real URIs) and search-by-name (local URIs)
            batch_artists = []
            search_artists = []
            for artist in artists_missing_genres:
                if ":local:" in artist.uri:
                    search_artists.append(artist)
                else:
                    batch_artists.append(artist)

            logger.info(
                "Found %d artist(s) without genres (%d by ID, %d by name search).",
                len(artists_missing_genres),
                len(batch_artists),
                len(search_artists),
            )

            # --- Batch fetch by Spotify ID ---
            batch_size = 50
            for i in range(0, len(batch_artists), batch_size):
                batch = batch_artists[i : i + batch_size]
                artist_ids = []
                uri_to_artist = {}

                for artist in batch:
                    parts = artist.uri.split(":")
                    if len(parts) == 3 and parts[1] == "artist":
                        artist_ids.append(parts[2])
                        uri_to_artist[artist.uri] = artist

                if not artist_ids:
                    continue

                try:
                    results = sp.artists(artist_ids)
                    for artist_data in results.get("artists", []):
                        if not artist_data:
                            continue
                        uri = artist_data.get("uri")
                        genres = artist_data.get("genres", [])
                        popularity = artist_data.get("popularity")

                        if uri and uri in uri_to_artist:
                            db_artist = uri_to_artist[uri]
                            db_artist.genres = genres if genres else []
                            if popularity is not None:
                                db_artist.popularity = popularity
                            updated_count += 1
                except Exception as e:
                    logger.error(
                        "Failed to fetch artist batch at index %d: %s", i, e
                    )
                    continue

            # --- Search by name for data-export artists ---
            for idx, artist in enumerate(search_artists):
                try:
                    results = sp.search(q=artist.name, type="artist", limit=1)
                    items = results.get("artists", {}).get("items", [])
                    if items:
                        top = items[0]
                        artist.genres = top.get("genres", []) or []
                        if top.get("popularity") is not None:
                            artist.popularity = top["popularity"]
                        updated_count += 1
                    else:
                        artist.genres = []  # no match found, mark as processed
                except Exception as e:
                    logger.error(
                        "Failed to search artist '%s': %s", artist.name, e
                    )
                    artist.genres = []  # mark as processed to avoid retrying

                # Respect Spotify rate limits — commit + brief pause every 50
                if (idx + 1) % 50 == 0:
                    session.commit()
                    logger.info(
                        "Searched %d/%d artists by name...",
                        idx + 1,
                        len(search_artists),
                    )
                    time.sleep(1)

            session.commit()

        logger.info("Genre sync complete: %d artist(s) updated.", updated_count)
    except Exception as e:
        logger.error("Failed to sync artist genres: %s", e)

    return updated_count
