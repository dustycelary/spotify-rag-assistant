import json
import logging
import os
from pathlib import Path

import spotipy

logger = logging.getLogger(__name__)


def remove_keys_recursive(data, keys_to_remove: set | list) -> any:
    """Recursively removes specified keys from nested dictionaries and lists."""
    if isinstance(data, dict):
        return {
            key: remove_keys_recursive(val, keys_to_remove)
            for key, val in data.items()
            if key not in keys_to_remove
        }
    elif isinstance(data, list):
        return [remove_keys_recursive(item, keys_to_remove) for item in data]
    return data


def add_track_to_queue(sp: spotipy.Spotify, track_query: str):
    """Gets closest matching track to query and adds it to queue of current user"""

    logger.info("Searching for track: '%s'", track_query)
    rapsody_uri = get_top_track_uri(
        sp,
        track_query,
    )

    if rapsody_uri:
        logger.info("Adding track to playback queue: %s", rapsody_uri)

        try:
            sp.add_to_queue(rapsody_uri)

        except Exception as e:
            logger.error("Failed to add track due to error: %s", e)

    else:
        logger.warning("Could not add track to queue: URI is missing.")


def get_recently_played_tracks(
    sp: spotipy.Spotify,
    save_path=None,
    remove_markets: bool = True,
    **kwargs,
) -> dict:
    """Fetch and optionally persist the current user's recently played tracks.

    Args:
        sp: Authenticated Spotipy client.
        track_limit: Maximum number of tracks to request from Spotify.
        save_path: Optional path to save the returned payload as JSON.
        remove_markets: Remove ``available_markets`` keys from the payload when True.
        **kwargs: Extra arguments forwarded to
            ``sp.current_user_recently_played`` (for example ``limit``, ``before`` and
            ``after``). Unsupported keys are handled by Spotipy/Spotify API errors.

    Returns:
        The recently played tracks payload returned by the Spotify API.
    """
    logger.info("Looking for recently played tracks")
    recently_played_tracks = sp.current_user_recently_played(**kwargs)
    if remove_markets:
        logger.info("Getting rid of available_markets key for recently played tracks")
        recently_played_tracks = remove_keys_recursive(
            recently_played_tracks, {"available_markets"}
        )

    if save_path:
        # data_home = Path(__file__).resolve().parent.parent / "test_data"
        # recently_played_path = data_home / "recently_played.json"
        save_json(recently_played_tracks, save_path)

    return recently_played_tracks


def save_json(data, file_path: Path | str) -> bool:
    """Saves a python json object to json file.

    It creates file, and any uncreated parent directories.

    Raises TypeError if data is not JSON-serializable"""
    if not file_path:
        logger.info("Failed to save data without a file_path")
        return False

    file_path = Path(file_path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

        logger.info("Successfully saved results to %s", os.path.abspath(file_path))
        return True

    except (TypeError, OverflowError):
        logger.error(
            "Serialization failed. Data is not JSON-serializable", exc_info=True
        )
        return False
    except OSError:
        logger.exception("Failed to save JSON to %s due to an I/O error", file_path)
        return False


def get_top_track_uri(
    sp: spotipy.Spotify, query: str, filename: Path | str | None = None
) -> str | None:
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
        logger.debug("Writing raw Spotify API response to %s", filename)
        cleaned_results = remove_keys_recursive(results, {"available_markets"})
        save_json(cleaned_results, filename)

    items = results["tracks"]["items"]
    if len(items) > 0:
        top_track = items[0]
        track_name = top_track["name"]
        track_uri = top_track["uri"]

        logger.info("Found track: '%s' (URI: %s)", track_name, track_uri)
        return track_uri

    logger.warning("No matching tracks found for query: '%s'", query)

    return None
