import logging
import os

import dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
db_host = os.environ.get("DB_HOST", "localhost")
DB_URI = f"postgresql+psycopg://dev_user:dev_password@{db_host}:5432/spotify_rag"

engine = create_engine(DB_URI)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    # db_host = os.environ.get("DB_HOST", "localhost")
    db = SessionLocal()
    try:
        yield db

    finally:
        db.close()


def init_db(engine):
    """Initializes the database by creating extensions and all schema tables."""
    try:
        # Import all models here so Base.metadata knows about them
        import src.models.artist  # noqa: F401
        import src.models.audio_features  # noqa: F401
        import src.models.embedding  # noqa: F401
        import src.models.lyrics  # noqa: F401
        import src.models.recently_played  # noqa: F401
        import src.models.track  # noqa: F401
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        Base.metadata.create_all(engine)
        logger.info("Database tables and extensions have been created")
    except Exception as e:
        logger.error(f"Failed to initialise database: {e}")
        raise e
