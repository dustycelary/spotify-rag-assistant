from datetime import datetime, timezone

import pytest

from src.import_spotify_history import parse_timestamp

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "2025-01-02T10:30:00Z",
            datetime(2025, 1, 2, 10, 30, tzinfo=timezone.utc),
        ),
        (
            "2025-01-02T10:30:00+00:00",
            datetime(2025, 1, 2, 10, 30, tzinfo=timezone.utc),
        ),
        (
            "2025-01-02T12:30:00+02:00",
            datetime(2025, 1, 2, 10, 30, tzinfo=timezone.utc),
        ),
        (
            "2025-01-02T05:30:00-05:00",
            datetime(2025, 1, 2, 10, 30, tzinfo=timezone.utc),
        ),
        (
            "2025-01-02 10:30",
            datetime(2025, 1, 2, 10, 30, tzinfo=timezone.utc),
        ),
    ],
    ids=[
        "iso-z",
        "iso-utc",
        "iso-positive-offset",
        "iso-negative-offset",
        "legacy-naive-utc",
    ],
)
def test_parse_timestamp_normalizes_valid_values_to_utc(
    raw: str, expected: datetime
) -> None:
    result = parse_timestamp(raw)
    assert result == expected
    assert result.tzinfo is timezone.utc


@pytest.mark.parametrize("raw", [None, "", 123, [], "invalid", "2025-02-30 10:00"])
def test_parse_timestamp_rejects_invalid_values(raw: object) -> None:
    assert parse_timestamp(raw) is None
