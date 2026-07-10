import logging
import os
import sys
from pathlib import (
    Path,
)

import dotenv
import spotipy
from spotipy.oauth2 import (
    SpotifyOAuth,
)

from utils.spotify_helpers import get_top_track_uri, remove_keys_recursive, save_json

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
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log", mode="a"),
        ],
    )

    logger.info("Starting ingest pipeline...")
    sp = authenticate_user()
    logger.info("Authentication successful.")

    # working test
    data_home = Path(__file__).resolve().parent.parent / "test_data"

    recently_played_path = data_home / "recently_played.json"
    recently_played_tracks = sp.current_user_recently_played()
    cleaned_tracks = remove_keys_recursive(
        recently_played_tracks, {"available_markets"}
    )
    save_json(cleaned_tracks, recently_played_path)

    query = "Bohemian rapsody Queen"
    logger.info("Searching for track: '%s'", query)
    rapsody_uri = get_top_track_uri(
        sp,
        query,
    )

    if rapsody_uri:
        logger.info("Adding track to playback queue: %s", rapsody_uri)

        try:
            sp.add_to_queue(rapsody_uri)

        except Exception as e:
            logger.error("Failed to add track due to error: %s", e)

    else:
        logger.warning("Could not add track to queue: URI is missing.")


if __name__ == "__main__":
    main()
