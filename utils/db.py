import logging
from abc import ABC, abstractmethod
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)

UTILS_DIR = Path(__file__).resolve().parent

SCHEMA_PATH = UTILS_DIR.parent / "pipeline" / "schema.sql"


def init_db(conn: psycopg2.extensions.connection):
    with conn.cursor() as cur:
        with open(SCHEMA_PATH) as f:
            schema_sql = f.read()

        cur.execute(schema_sql)

    conn.commit()
    logger.info("Database tables have been created")


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
