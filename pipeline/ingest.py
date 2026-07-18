import logging
import os
import sys
from pathlib import Path

# Ensure project root is in the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dotenv
import psycopg2
import spotipy
from pipeline.db import init_db
from spotipy.oauth2 import (
    SpotifyOAuth,
)

from rag import ragcontroller

# TODO: adding spotify api so mac can set GET http requests
# TODO: add a feature allowing someone to import data from spotify,
# so app can have whole history
dotenv.load_dotenv()
CLIENT_ID = os.environ.get("client_id")
CLIENT_SECRET = os.environ.get("client_secret")
REDIRECT_URI = os.environ.get("redirect_uri")
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
CACHE_PATH = ".spotify_token_cache"

logger = logging.getLogger(__name__)


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
        # level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log", mode="a"),
        ],
    )
    db_host = os.environ.get("DB_HOST", "localhost")
    conn = psycopg2.connect(
        f"postgresql://dev_user:dev_password@{db_host}:5432/spotify_rag"
    )
    init_db(conn)

    logger.info("Starting ingest pipeline...")
    sp = authenticate_user()  # noqa: F841
    logger.info("Authentication successful.")
    user_question = input("What would you like to know about your spotify data?: ")
    rag = ragcontroller.RagController(conn)
    print(f"RESPONSE:\n\n {rag.query(user_question)}")

    # data_home = Path(__file__).resolve().parent.parent / "test_data"
    # recently_played_path = data_home / "recently_played.json"
    # recents = get_recently_played_tracks(sp, recently_played_path)


if __name__ == "__main__":
    main()
