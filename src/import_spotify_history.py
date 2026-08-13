#!/usr/bin/env python3
"""
Spotify Streaming History Importer
===================================
Imports Spotify listening history (from Spotify Extended Privacy Data download:
endsong_*.json, Audio_*.json, or StreamingHistory*.json) into PostgreSQL
database tables.
Also enriches `audio_features` and `embeddings` post-import.

Usage:
    # Append new history to existing database
    python src/import_spotify_history.py

    # Specify custom path to JSON files/folder
    python src/import_spotify_history.py --path /path/to/json_folder

    # Reset database (truncate all tables) before importing
    python src/import_spotify_history.py --reset
"""

import argparse
import json
import logging
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup project path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dotenv

dotenv.load_dotenv(PROJECT_ROOT / ".env")

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


def clean_slug(text: str) -> str:
    """Generates a clean string slug for fallback URIs."""
    return re.sub(r"[^a-z0-9]", "_", text.lower()).strip("_")


def parse_timestamp(ts_val: str) -> datetime | None:
    """Parses various Spotify timestamp formats into UTC datetime object."""
    if not ts_val:
        return None
    try:
        if "T" in ts_val:
            return datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
        return datetime.strptime(ts_val, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.debug("Failed to parse timestamp '%s': %s", ts_val, e)
        return None


def truncate_all_tables():
    """Truncates all database tables in public schema with CASCADE."""
    logger.info("Truncating all existing database tables...")
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
            )
        )
        tables = [r[0] for r in res if r[0] != "spatial_ref_sys"]
        if tables:
            tables_str = ", ".join([f'"{t}"' for t in tables])
            conn.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE;"))
            logger.info("Successfully truncated tables: %s", ", ".join(tables))

    logger.info("Re-initializing database schema & views...")
    init_db(engine)


def discover_json_files(target_path: Path) -> list[Path]:
    """Finds all Spotify streaming history JSON files in target directory or file."""
    if target_path.is_file():
        return [target_path]
    if target_path.is_dir():
        files = list(target_path.glob("*.json"))
        return sorted(files)
    return []


def parse_spotify_history_files(json_files: list[Path]):
    """Parses Spotify history JSON files and extracts structured records."""
    tracks_dict = {}
    artists_dict = {}
    track_artists_set = set()
    plays_list = []
    total_records_read = 0

    for filepath in json_files:
        logger.info("Parsing history file: %s", filepath.name)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to read JSON file %s: %s", filepath, e)
            continue

        if not isinstance(data, list):
            logger.warning(
                "File %s does not contain a list of records. Skipping.", filepath.name
            )
            continue

        for item in data:
            total_records_read += 1

            track_uri = (
                item.get("spotify_track_uri")
                or item.get("track_uri")
                or item.get("uri")
            )
            track_name = (
                item.get("master_metadata_track_name")
                or item.get("trackName")
                or item.get("title")
            )
            artist_name = (
                item.get("master_metadata_album_artist_name")
                or item.get("artistName")
                or item.get("artist")
            )
            album_name = (
                item.get("master_metadata_album_album_name")
                or item.get("albumName")
                or item.get("album")
            )
            ts_val = item.get("ts") or item.get("endTime") or item.get("played_at")
            ms_played = item.get("ms_played") or 0

            # Create fallback local URI for older history without explicit URI
            if not track_uri and (track_name and artist_name):
                safe_name = clean_slug(f"{artist_name}_{track_name}")
                track_uri = f"spotify:track:local:{safe_name}"

            if not track_uri or not ts_val:
                continue

            played_at = parse_timestamp(ts_val)
            if not played_at:
                continue

            # Track entry
            if track_uri not in tracks_dict:
                tracks_dict[track_uri] = {
                    "uri": track_uri,
                    "title": track_name or "Unknown Title",
                    "album_name": album_name,
                    "duration_ms": ms_played,
                }
            elif ms_played > (tracks_dict[track_uri]["duration_ms"] or 0):
                tracks_dict[track_uri]["duration_ms"] = ms_played

            # Artist & Track-Artist relationship
            if artist_name:
                artist_uri = f"spotify:artist:local:{clean_slug(artist_name)}"
                if artist_uri not in artists_dict:
                    artists_dict[artist_uri] = {
                        "uri": artist_uri,
                        "name": artist_name,
                    }
                track_artists_set.add((track_uri, artist_uri))

            # Played History entry
            plays_list.append(
                {
                    "track_uri": track_uri,
                    "played_at": played_at,
                    "context_type": item.get("inc_context_type")
                    or item.get("context_type"),
                    "context_uri": item.get("inc_context_uri")
                    or item.get("context_uri"),
                }
            )

    return total_records_read, tracks_dict, artists_dict, track_artists_set, plays_list


def bulk_insert_records(
    tracks_dict, artists_dict, track_artists_set, plays_list, chunk_size=5000
):
    """Inserts records in chunks using PostgreSQL bulk upsert."""
    t0 = time.time()
    with SessionLocal() as session:
        # 1. Tracks
        logger.info("Inserting %d unique tracks...", len(tracks_dict))
        track_values = list(tracks_dict.values())
        for i in range(0, len(track_values), chunk_size):
            chunk = track_values[i : i + chunk_size]
            stmt = (
                pg_insert(Track)
                .values(chunk)
                .on_conflict_do_nothing(index_elements=["uri"])
            )
            session.execute(stmt)

        # 2. Artists
        logger.info("Inserting %d unique artists...", len(artists_dict))
        artist_values = list(artists_dict.values())
        for i in range(0, len(artist_values), chunk_size):
            chunk = artist_values[i : i + chunk_size]
            stmt = (
                pg_insert(Artist)
                .values(chunk)
                .on_conflict_do_nothing(index_elements=["uri"])
            )
            session.execute(stmt)

        # 3. Track-Artists
        logger.info(
            "Inserting %d track-artist relationships...", len(track_artists_set)
        )
        ta_values = [
            {"track_uri": tu, "artist_uri": au} for (tu, au) in track_artists_set
        ]
        for i in range(0, len(ta_values), chunk_size):
            chunk = ta_values[i : i + chunk_size]
            stmt = (
                pg_insert(track_artists)
                .values(chunk)
                .on_conflict_do_nothing(index_elements=["track_uri", "artist_uri"])
            )
            session.execute(stmt)

        # 4. Played History
        logger.info("Inserting %d listening history records...", len(plays_list))
        for i in range(0, len(plays_list), chunk_size):
            chunk = plays_list[i : i + chunk_size]
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
            PROJECT_ROOT / "playground" / "Spotify Extended Streaming History",
            PROJECT_ROOT / "playground" / "spotify_data",
            PROJECT_ROOT / "test_data",
            PROJECT_ROOT / "data",
            PROJECT_ROOT,
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
