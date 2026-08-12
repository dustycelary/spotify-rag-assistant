import argparse
import logging
import os
import sys

import dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Ensure project root is in sys.path when invoked via python -m src/main.py or direct script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.agent_context import describe_schema
from src.agent_tools import answer_question
from src.db import SessionLocal, engine, init_db

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME")
CLIENT_ID = os.environ.get("client_id")
CLIENT_SECRET = os.environ.get("client_secret")
REDIRECT_URI = os.environ.get("redirect_uri")
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


def authenticate_user() -> spotipy.Spotify:
    """Returns spotiy.Spotify instance after authenticating user
    and saving token to CACHE_PATH"""

    if not all(
        [
            CLIENT_ID,
            CLIENT_SECRET,
            REDIRECT_URI,
        ]
    ):
        logger.error(
            "Missing credentials in .env file: "
            "client_id, client_secret, or redirect_uri"
        )
        sys.exit(1)

    logger.info("Authenticating user with Spotify OAuth...")
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=PI_SCOPES,
            open_browser=False,
            cache_path=CACHE_PATH,
        )
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Spotify RAG Assistant")
    parser.add_argument(
        "-lc",
        "--log-console",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable or disable logging to console (default: False). Logs are always written to app.log.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Shortcut to enable console logging.",
    )
    args, _ = parser.parse_known_args()
    return args.log_console or args.verbose


def main():
    log_console = parse_args()

    if not log_console:
        os.environ["TQDM_DISABLE"] = "1"  # disables progress bars
        # disables symlink symlink warnings from hugging Face
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        # disables tokenizer deadlock warnings
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

    handlers = [logging.FileHandler("app.log", mode="a")]
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

    logger.info("Initializing database...")
    init_db(engine)
    schema_layout = describe_schema(engine)

    logger.info("Starting ingest pipeline...")
    # sp = authenticate_user()
    # logger.info("Authentication successful.")

    # from src.helpers import sync_spotify_to_db
    #
    # sync_spotify_to_db(sp)

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2")
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

        with SessionLocal() as session:
            ans = answer_question(user_question, session, model, schema_layout)
            print(f"\n{ans}\n")


if __name__ == "__main__":
    main()
