import json
import os

import spotipy


def save_json(data, filename="test_file.json"):

    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

        print(f"Successfully saved results to {os.path.abspath(filename)}")

    except Exception as e:
        print(f"Error saving file: {e}")


def get_top_track_uri(sp: spotipy.Spotify, query: str, filename) -> str:
    """Searches Spotify for a track matching the query and returns its URI.

    This helper performs a track search, writes the raw search results to a
    local test file for debugging, and extracts the URI of the top search result.

    Args:
        sp (spotipy.Spotify): An authenticated Spotify client instance.
        query (str): The search term (e.g., track title, artist).

    Returns:
        str: The Spotify URI of the top track matching the query if found,
         otherwise None.
    """
    results = sp.search(q=query, type="track", limit=1)
    if filename:
        save_json(results, filename)

    items = results["tracks"]["items"]
    if len(items) > 0:
        top_track = items[0]
        track_name = top_track["name"]
        track_uri = top_track["uri"]

        print(f"Found track: {track_name}")
        print(f"Track URI: {track_uri}")
        return track_uri

    print("No matching tracks")

    return None
