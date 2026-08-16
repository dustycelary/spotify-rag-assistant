from datetime import datetime, timezone

import pytest

from src.import_spotify_history import parse_timestamp


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (
            "2025-01-02T10:30:00Z",
            datetime(2025, 1, 2, 10, 30, 0, tzinfo=timezone.utc),
        ),
        (
            "2025-01-02T10:30:00+00:00",
            datetime(2025, 1, 2, 10, 30, 0, tzinfo=timezone.utc),
        ),
        (
            "2025-01-02 10:30",
            datetime(2025, 1, 2, 10, 30, tzinfo=timezone.utc),
        ),
    ],
    ids=["iso-z", "iso-offset", "legacy-format"],
)
def test_parse_timestamp_valid(input: str, expected: datetime) -> None:
    result = parse_timestamp(input)
    assert result == expected
    assert result.tzinfo is not None


def test_parse_timestamp_invalid() -> None:
    assert parse_timestamp(None) is None
    assert parse_timestamp("not timestamp") is None
    assert parse_timestamp("00:00:99Z") is None
