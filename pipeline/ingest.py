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

from utils.spotify_helpers import (
    get_top_track_uri,
)

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
        print("You must have CLIENT_ID, CLIENT_SECRET, AND REDIRECT_URI in .env file")

        sys.exit(1)

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

    sp = authenticate_user()

    # working test
    script_dir = Path(__file__).resolve().parent
    test_path = script_dir.parent / "test" / "test.json"
    rapsody_uri = get_top_track_uri(
        sp,
        "Bohemian rapsody Queen",
        str(test_path),
    )

    sp.add_to_queue(rapsody_uri)


if __name__ == "__main__":
    main()
