import pytest

from src.import_spotify_history import generate_local_uri, normalise_history_record

pytestmark = pytest.mark.unit


def test_local_track_uri_is_stable() -> None:
    """generate the same track URI twice from identical artist/title data."""
    uri1 = generate_local_uri("track", "The Beatles", "Hey Jude")
    uri2 = generate_local_uri("track", "  the beatles  ", "  HEY JUDE  ")

    assert uri1 == uri2
    assert uri1.startswith("spotify:track:local:v1:")


def test_local_track_uri_is_non_empty_for_unicode_identity() -> None:
    uri = generate_local_uri("track", "✨✨", "🎶🎶")

    assert uri.startswith("spotify:track:local:v1:")
    parts = uri.split(":")
    assert len(parts) == 6
    assert parts[4] != ""  # Non-empty slug/fallback
    assert len(parts[5]) == 12  # 12-character SHA-256 hash prefix


def test_different_identities_with_same_slug_do_not_collide() -> None:
    """choose two identities that slugify alike but canonicalize differently."""
    uri1 = generate_local_uri("track", "Artist", "Track 1")
    uri2 = generate_local_uri("track", "Artist", "Track-1")

    assert uri1 != uri2
    parts1 = uri1.split(":")
    parts2 = uri2.split(":")
    assert parts1[4] == parts2[4]  # Same slug portion
    assert parts1[5] != parts2[5]  # Hash portion prevents collision


def test_local_artist_uri_is_collision_resistant() -> None:
    """repeat the collision check for artist identities."""
    uri1 = generate_local_uri("artist", "The Band")
    uri2 = generate_local_uri("artist", "The-Band")

    assert uri1.startswith("spotify:artist:local:v1:")
    assert uri2.startswith("spotify:artist:local:v1:")
    assert uri1 != uri2
    parts1 = uri1.split(":")
    parts2 = uri2.split(":")
    assert parts1[4] == parts2[4]  # Same slug portion
    assert parts1[5] != parts2[5]  # Hash portion prevents collision


def test_real_spotify_uri_is_preserved() -> None:
    """normalize a record containing a real spotify:track URI."""
    record = {
        "spotify_track_uri": "spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
        "master_metadata_track_name": "Teardrop",
        "master_metadata_album_artist_name": "Massive Attack",
        "ts": "2025-01-01T12:00:00Z",
        "ms_played": 210000,
    }

    norm = normalise_history_record(record)
    assert norm is not None
    assert norm.track_uri == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
    assert "local:v1" not in norm.track_uri
