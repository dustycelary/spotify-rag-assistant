import logging
import os
import sys

import dotenv
import spotipy
from sentence_transformers import SentenceTransformer
from spotipy.oauth2 import SpotifyOAuth

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


def main():
    # Configure global logging settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log", mode="a"),
        ],
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
