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
