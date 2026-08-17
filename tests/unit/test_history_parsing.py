import json
from pathlib import Path

import pytest

from src.import_spotify_history import (
    discover_json_files,
    generate_local_uri,
    parse_spotify_history_files,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def spotify_fixture_dir() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "spotify"


def test_playback_duration_is_not_track_duration(spotify_fixture_dir: Path) -> None:
    res = parse_spotify_history_files([spotify_fixture_dir / "extended_history.json"])
    track = res.tracks_by_uri["spotify:track:fictional001"]
    assert track["duration_ms"] is None

    play = next(p for p in res.plays if p["track_uri"] == "spotify:track:fictional001")
    assert play["playback_ms"] == 182000


def test_missing_uri_generates_local_uri_with_complete_identity(
    spotify_fixture_dir: Path,
) -> None:
    res = parse_spotify_history_files([spotify_fixture_dir / "extended_history.json"])
    expected_uri = generate_local_uri("track", "Velvet Horizon", "Echoes in Blue")
    assert expected_uri in res.tracks_by_uri
    assert res.tracks_by_uri[expected_uri]["title"] == "Echoes in Blue"

    plays = [p for p in res.plays if p["track_uri"] == expected_uri]
    assert len(plays) == 1


def test_missing_uri_and_identity_is_skipped(spotify_fixture_dir: Path) -> None:

    res = parse_spotify_history_files([spotify_fixture_dir / "extended_history.json"])
    assert "" not in res.tracks_by_uri
    assert None not in res.tracks_by_uri
    assert not any(p["track_uri"] is None or p["track_uri"] == "" for p in res.plays)


def test_missing_artist_does_not_create_artist(spotify_fixture_dir: Path) -> None:

    res = parse_spotify_history_files([spotify_fixture_dir / "extended_history.json"])
    track_uri = "spotify:track:fictional_noartist"
    assert track_uri in res.tracks_by_uri
    assert res.tracks_by_uri[track_uri]["title"] == "Anonymous Drift"

    artist_pairs = [pair for pair in res.track_artist_pairs if pair[0] == track_uri]
    assert len(artist_pairs) == 0


def test_real_uri_without_title_uses_unknown_title(spotify_fixture_dir: Path) -> None:

    res = parse_spotify_history_files([spotify_fixture_dir / "extended_history.json"])
    track_uri = "spotify:track:fictional_notitle"
    assert track_uri in res.tracks_by_uri
    assert res.tracks_by_uri[track_uri]["title"] == "Unknown Title"


def test_invalid_duration_becomes_zero(spotify_fixture_dir: Path) -> None:

    ext_res = parse_spotify_history_files(
        [spotify_fixture_dir / "extended_history.json"]
    )
    ext_play = next(
        p for p in ext_res.plays if p["track_uri"] == "spotify:track:fictional002"
    )
    assert ext_play["playback_ms"] == 0


def test_invalid_json_does_not_prevent_valid_file(
    spotify_fixture_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:

    res = parse_spotify_history_files(
        [
            spotify_fixture_dir / "malformed_json.json",
            spotify_fixture_dir / "extended_history.json",
        ]
    )
    assert res.total_records_read > 0
    assert "spotify:track:fictional001" in res.tracks_by_uri


def test_non_list_root_is_skipped(spotify_fixture_dir: Path) -> None:

    res = parse_spotify_history_files([spotify_fixture_dir / "malformed_root.json"])
    assert res.total_records_read == 0
    assert len(res.plays) == 0
    assert len(res.tracks_by_uri) == 0


def test_non_mapping_record_is_skipped(tmp_path: Path) -> None:

    mixed_file = tmp_path / "mixed.json"
    content = [
        "just a string",
        12345,
        {
            "ts": "2025-01-02T10:30:00Z",
            "spotify_track_uri": "spotify:track:scalar_test",
            "master_metadata_track_name": "Scalar Test Track",
            "ms_played": 100000,
        },
    ]
    mixed_file.write_text(json.dumps(content), encoding="utf-8")

    res = parse_spotify_history_files([mixed_file])
    assert res.total_records_read == 1
    assert "spotify:track:scalar_test" in res.tracks_by_uri
    assert len(res.plays) == 1


def test_file_discovery_is_sorted_and_json_only(tmp_path: Path) -> None:

    (tmp_path / "b.json").write_text("[]", encoding="utf-8")
    (tmp_path / "a.json").write_text("[]", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("text file", encoding="utf-8")

    discovered = discover_json_files(tmp_path)
    assert discovered == [tmp_path / "a.json", tmp_path / "b.json"]


def test_repeated_metadata_creates_one_track(spotify_fixture_dir: Path) -> None:

    res = parse_spotify_history_files(
        [
            spotify_fixture_dir / "overlapping_history.json",
            spotify_fixture_dir / "extended_history.json",
        ]
    )
    assert "spotify:track:fictional001" in res.tracks_by_uri
    track_count = sum(
        1 for uri in res.tracks_by_uri if uri == "spotify:track:fictional001"
    )
    assert track_count == 1

    fictional001_plays = [
        p for p in res.plays if p["track_uri"] == "spotify:track:fictional001"
    ]
    assert len(fictional001_plays) >= 3
