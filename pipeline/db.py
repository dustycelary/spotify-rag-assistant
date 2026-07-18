import logging
from abc import ABC, abstractmethod
from pathlib import Path

import psycopg2
from pipeline.track import Track

logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).resolve().parent
SCHEMA_DIR = PIPELINE_DIR / "schema"

# TODO: make function to get track lyrics
# TODO: add testing
# TODO: create teh methods and calss for tracks repository, (the SOLID principle idea)
# NOTE: plan out all the method signatures before doing htem


class BaseRepository(ABC):
    """Abstract interface for database repositories"""

    @abstractmethod
    def add(self, item):
        """Saves a entity dict to db"""
        pass

    @abstractmethod
    def get_by_id(self, entity_id) -> dict:
        """Retries entity by id string"""
        pass


class SqlTracksRepository(BaseRepository):
    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn

    def add(self, track: Track) -> None:
        query = """
            INSERT INTO tracks (uri, title, artist, release_date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (uri) DO NOTHING;
        """

        with self.conn.cursor() as cur:
            cur.execute(
                query, (track.uri, track.name, track.artist, track.release_date)
            )
        self.conn.commit()

    def get_by_id(self, entity_id: str) -> dict | None:
        query = """
            SELECT uri, title, artist, release_date FROM tracks WHERE uri = %s;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (entity_id,))
            row = cur.fetchone()
            if row:
                return {
                    "uri": row[0],
                    "title": row[1],
                    "artist": row[2],
                    "release_date": row[3],
                }
        return None


def init_db(conn: psycopg2.extensions.connection):
    """Initializes the database by executing all schema files sequentially.

    This function scans the designated schema directory, sorts the SQL files
    alphabetically, and runs them inside a single database transaction. If
    any file fails to execute, the entire transaction is rolled back.

    Args:
        conn (psycopg2.extensions.connection): An active database connection object.

    Raises:
        FileNotFoundError: If the schema directory does not exist or contains no files.
        psycopg2.DatabaseError: If a SQL syntax error or constraint violation occurs
            while executing the schema files.
    """
    try:
        sql_files = sorted(SCHEMA_DIR.glob("*.sql"))
        if not sql_files:
            logger.warning(f"No sql files found in directory {SCHEMA_DIR}")
            return

        with conn.cursor() as cur:
            for file_path in sql_files:
                logger.info(f"Executing schema file: {file_path}")

                with open(file_path) as f:
                    schema_sql = f.read()

                cur.execute(schema_sql)

        conn.commit()
        logger.info("Database tables have been created")

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialise database: {e}")
        raise e
