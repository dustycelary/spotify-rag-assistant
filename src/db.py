import logging
import os

import dotenv
import psycopg2  # noqa: F401
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_USER = os.environ.get("DB_USER", "")
DB_PORT = os.environ.get("DB_PORT", 5432)

database_url = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Import all models at module level so Base.metadata knows about them
# and mappers compile correctly whenever db is imported.
import src.models.artist  # noqa: F401
import src.models.audio_features  # noqa: F401
import src.models.embedding  # noqa: F401
import src.models.lyrics  # noqa: F401
import src.models.played_history  # noqa: F401
import src.models.track  # noqa: F401


def init_db(engine):
    """Initializes the database by creating extensions, all schema tables, and views."""
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))

        Base.metadata.create_all(engine)

        view_sql = """DROP VIEW IF EXISTS v_listening_history CASCADE;
   CREATE VIEW v_listening_history AS
   SELECT 
       ph.id AS history_id,
       ph.played_at,
       t.uri AS track_uri,
       t.title AS track_title,
       t.album_name,
       t.release_date,
       t.popularity,
       ROUND(t.duration_ms / 1000.0, 1) AS duration_seconds,
       COALESCE(string_agg(DISTINCT a.name, ', '), 'Unknown Artist') AS artist_names,
       (SELECT string_agg(DISTINCT g, ', ')
        FROM track_artists ta_g
        JOIN artists a_g ON ta_g.artist_uri = a_g.uri,
        LATERAL unnest(a_g.genres) AS g
        WHERE ta_g.track_uri = t.uri
       ) AS artist_genres,
       af.tempo,
       af.energy,
       af.danceability,
       af.valence
   FROM played_history ph
   JOIN tracks t ON ph.track_uri = t.uri
   LEFT JOIN track_artists ta ON t.uri = ta.track_uri
   LEFT JOIN artists a ON ta.artist_uri = a.uri
   LEFT JOIN audio_features af ON t.uri = af.track_uri
   GROUP BY ph.id, ph.played_at, t.uri, t.title, t.album_name, t.release_date, t.popularity, t.duration_ms, af.tempo, af.energy, af.danceability, af.valence;
"""

        with engine.begin() as conn:
            conn.execute(text(view_sql))

        logger.info("Database tables, extensions, and views have been created")
    except Exception as e:
        logger.error(f"Failed to initialise database: {e}")
        raise e
