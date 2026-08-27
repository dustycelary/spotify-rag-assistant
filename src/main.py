import argparse
import logging
import os
import sys
from pathlib import Path

import dotenv
import ollama
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy import text

# Ensure the project root is in sys.path when invoked as a module or direct script.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

CACHE_PATH = ".spotify_token_cache"
PI_SCOPES = (
    "user-modify-playback-state "
    "user-library-read "
    "user-library-modify "
    "playlist-read-private "
    "playlist-read-collaborative "
    "playlist-modify-public "
    "user-top-read "
    "user-read-recently-played"
)


class EmbedModel:
    """Loads embedding model on first use, not on startup."""

    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None

    def encode(self, *args, **kwargs):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model.encode(*args, **kwargs)


def validate_environment(ollama_model_name: str, embedding_model_name: str | None):
    """Validate configuration and dependencies, then return runtime objects."""
    required = ("DB_NAME", "DB_USER", "DB_PASSWORD", "EMBEDDING_MODEL_NAME")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        logger.error("Missing required settings: %s", ", ".join(missing))
        raise SystemExit(1)

    try:
        from src.db import SessionLocal, engine, init_db

        init_db(engine)
        with SessionLocal() as session:
            count = (
                session.execute(text("SELECT COUNT(*) FROM played_history")).scalar()
                or 0
            )
    except Exception as exc:
        logger.error(
            "PostgreSQL unavailable: %s. Run `docker compose up -d db` and "
            "check the DB_* settings.",
            exc,
        )
        raise SystemExit(1) from exc

    if count == 0:
        logger.warning(
            "Database is empty. Import history with "
            "`python src/import_spotify_history.py --path <export-path>`."
        )
    else:
        logger.info("Database ready (%d listening records).", count)

    try:
        ollama.Client().show(ollama_model_name)
    except Exception as exc:
        logger.error(
            "Ollama or model '%s' unavailable: %s. Start Ollama and run "
            "`ollama pull %s`.",
            ollama_model_name,
            exc,
            ollama_model_name,
        )
        raise SystemExit(1) from exc

    model = EmbedModel(embedding_model_name)
    try:
        model.encode(["startup check"])
    except Exception as exc:
        logger.error("Embedding model unavailable: %s", exc)
        raise SystemExit(1) from exc

    logger.info("Ollama and embedding models ready.")
    return SessionLocal, model


def authenticate_user() -> spotipy.Spotify:
    """Returns spotiy.Spotify instance after authenticating user
    and saving token to CACHE_PATH"""

    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")
    if not all((client_id, client_secret, redirect_uri)):
        logger.error(
            "Missing credentials in .env file: "
            "client_id, client_secret, or redirect_uri"
        )
        sys.exit(1)

    logger.info("Authenticating user with Spotify OAuth...")
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=PI_SCOPES,
            open_browser=False,
            cache_path=CACHE_PATH,
        )
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Spotify RAG Assistant")
    parser.add_argument(
        "--log-console",
        action="store_true",
        help="Also write logs to the console. Logs are always written to logs/app.log.",
    )
    args = parser.parse_args()
    return args.log_console


def main():
    log_console = parse_args()

    if not log_console:
        os.environ["TQDM_DISABLE"] = "1"  # disables progress bars
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = (
            "1"  # disables symlink symlink warnings from hugging Face
        )
        os.environ["TOKENIZERS_PARALLELISM"] = (
            "false"  # disables tokenizer deadlock warnings
        )

    log_path = Path("logs/app.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_path, mode="a")]
    if log_console:
        handlers.append(logging.StreamHandler(sys.stdout))

    # Capture warnings (like HuggingFace hub warnings) into python logging
    logging.captureWarnings(True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    embedding_model = os.environ.get("EMBEDDING_MODEL_NAME")
    session_factory, model = validate_environment(ollama_model, embedding_model)
    from src.agent_tools import answer_question

    # sp = authenticate_user()
    # logger.info("Authentication successful.")

    logger.info(f"Using Ollama LLM model: {ollama_model}")

    print("Ready! Type 'exit' or 'quit' to stop.")

    while True:
        user_question = input(
            "What would you like to know about your spotify data?: "
        ).strip()
        if not user_question:
            continue
        if user_question.lower() in ["exit", "quit"]:
            break

        with session_factory() as session:
            ans = answer_question(user_question, session, model)
            print(f"\n{ans}\n")


if __name__ == "__main__":
    main()
