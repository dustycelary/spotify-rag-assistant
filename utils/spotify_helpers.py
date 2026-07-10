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
