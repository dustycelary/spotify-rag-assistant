import pytest

from src.agent_tools import clean_sql, validate_sql


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "```sql\nSELECT * FROM v_listening_history;\n```",
            "SELECT * FROM v_listening_history",
        ),
        (
            "  SELECT * FROM v_listening_history;  ",
            "SELECT * FROM v_listening_history",
        ),
        (
            "SELECT 'one;two' FROM v_listening_history;",
            "SELECT 'one;two' FROM v_listening_history",
        ),
        (
            "SELECT * FROM v_listening_history WHERE track_title LIKE '%rock%';",
            "SELECT * FROM v_listening_history WHERE track_title LIKE '%rock%'",
        ),
    ],
)
def test_clean_sql(raw, expected):
    assert clean_sql(raw) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM v_listening_history",
        "SELECT COUNT(*) FROM v_listening_history",
        "SELECT * FROM public.v_listening_history",
        'SELECT * FROM "v_listening_history"',
        """
        WITH recent AS (
            SELECT *
            FROM v_listening_history
            WHERE played_at >= CURRENT_DATE - INTERVAL '7 days'
        )
        SELECT track_title, COUNT(*)
        FROM recent
        GROUP BY track_title
        """,
        """
        SELECT track_title FROM v_listening_history
        UNION
        SELECT track_title FROM v_listening_history
        """,
        """
        SELECT *
        FROM (
            SELECT * FROM v_listening_history
        ) AS history
        """,
        """
        SELECT 'Delete Me; Drop It'
        FROM v_listening_history
        """,
        """
        SELECT *
        FROM v_listening_history
        /* DROP TABLE tracks; */
        """,
    ],
)
def test_validate_sql_accepts_safe_queries(sql):
    assert validate_sql(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "-- comment only",
        "SELECT 1",
        "SELECT * FROM tracks",
        "SELECT * FROM artists",
        "SELECT * FROM public.tracks CROSS JOIN v_listening_history",
        'SELECT * FROM "tracks" CROSS JOIN v_listening_history',
        "SELECT * FROM private.v_listening_history",
        """
        SELECT *
        FROM v_listening_history
        UNION
        SELECT * FROM tracks
        """,
        """
        SELECT *
        FROM (
            SELECT * FROM tracks
        ) AS raw_tracks
        CROSS JOIN v_listening_history
        """,
        "SELECT * FROM v_listening_history; SELECT * FROM tracks",
        "INSERT INTO tracks (uri, title) VALUES ('x', 'x')",
        "UPDATE tracks SET title = 'x'",
        "DELETE FROM tracks",
        "DROP TABLE tracks",
        "ALTER TABLE tracks ADD COLUMN bad integer",
        "CREATE TABLE bad (id integer)",
        "TRUNCATE tracks",
        "SELECT * INTO copied_history FROM v_listening_history",
        """
        WITH removed AS (
            DELETE FROM tracks RETURNING *
        )
        SELECT * FROM v_listening_history
        """,
        "SELECT * FROM (",
    ],
)
def test_validate_sql_rejects_unsafe_queries(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)
