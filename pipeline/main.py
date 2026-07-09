import os

import dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

dotenv.load_dotenv()
CLIENT_ID = os.environ.get("client_id")
CLIENT_SECRET = os.environ.get("client_secret")
REDIRECT_URI = os.environ.get("redirect_uri")
PI_SCOPES = "user-library-read user-library-modify playlist-read-private playlist-read-collaborative playlist-modify-public user-top-read user-read-recently-played"

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=PI_SCOPES,
        open_browser=False,
        cache_path=".spotify_token_cache",
    )
)

# connection test
try:
    user = sp.current_user()
    print(f"Successfully authenticated as: {user['display_name']}")
except Exception as e:
    print(f"Authentication setup required: {e}")
