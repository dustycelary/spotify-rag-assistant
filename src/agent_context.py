from datetime import datetime

VIEW_SCHEMA = """\
`v_listening_history` columns:
- history_id integer; played_at timestamp; track_uri text
- track_title text; album_name text; release_date date
- popularity integer (0-100); duration_seconds numeric
- artist_names text; artist_genres comma-separated text
- tempo numeric (BPM); energy, danceability, valence numeric (0-1)
- played_time integer: milliseconds listened during this event
- played_time_seconds numeric: seconds listened during this event
- duration_seconds numeric: the track's full duration
"""


def build_system_prompt(reference_time: datetime | None = None) -> str:
    now = reference_time or datetime.now().astimezone()

    return f"""\
Answer questions about the user's Spotify history. Use a tool before stating facts.
Current local time: {now.isoformat(timespec="seconds")}.

SQL may query only this view:
{VIEW_SCHEMA}
Use SQL for events, dates, metadata, counts, rankings, genres, and audio metrics.
Use semantic search for subjective qualities supplied by the user. For similarity
to a named track, retrieve its genres and metrics with SQL first; never invent them.
For listening-time questions, calculate from played_time.
Never use duration_seconds as a substitute because it is the full track duration.

Issue one tool call at a time without explanatory prose. SQL must be one SELECT or
WITH...SELECT. Use raw rows for event lists and aggregation for summaries. Use
half-open date ranges. Group selected non-aggregate fields. Filter genres only with
`artist_genres ILIKE '%genre%'`. Choose a LIMIT appropriate to the user's request.
For overall top N items broken down by period, select the top N in a CTE, then join
it back to history and aggregate by period in one query.

Tool errors are not evidence. Base answers only on returned values. Explain semantic
matches only with returned genres and metrics. State when no matches exist. Respond
in concise English.
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": (
                "Query listening events, metadata, counts, rankings, genres "
                "or audio metrics using v_listening_history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "One read-only PostgreSQL SELECT or WITH...SELECT "
                            "against v_listening_history."
                        ),
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": (
                "Find tracks matching user-supplied or previously retrieved "
                "musical qualities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "description": (
                            "Grounded mood, genre and audio characteristics."
                        ),
                    }
                },
                "required": ["query_text"],
            },
        },
    },
]

SYSTEM_PROMPT = build_system_prompt()
