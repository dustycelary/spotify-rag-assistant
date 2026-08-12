from sqlalchemy import inspect


def describe_schema(
    engine,
    tables=(
        "artists",
        "audio_features",
        "embeddings",
        "lyrics",
        "played_history",
        "tracks",
        "v_listening_history",
    ),
):
    insp = inspect(engine)
    lines = []
    existing_tables = set(insp.get_table_names())

    for t in tables:
        if t in existing_tables:
            cols = [f"{c['name']} ({c['type']})" for c in insp.get_columns(t)]
            lines.append(f"{t}: {', '.join(cols)}")

    return "\n".join(lines)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": "Execute a PostgreSQL SELECT query to get structured counts, rankings, history, timestamps, top songs, or specific song metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Valid PostgreSQL SELECT query against v_listening_history or other tables.",
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
                "Perform vector similarity search on track embeddings based on musical vibe, mood, genres, "
                "tempo, energy, or acoustic style. Use this tool when recommending tracks based on subjective feel or similarity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "description": (
                            "Rich descriptive string detailing the desired music vibe, genres, mood, acoustic attributes, or tempo "
                            "(e.g., 'upbeat synth pop emotional narrative ballad', 'chill acoustic indie folk with warm vocals'). "
                            "DO NOT pass plain artist names or bare song titles alone; expand them into descriptive musical qualities."
                        ),
                    }
                },
                "required": ["query_text"],
            },
        },
    },
]

SYSTEM_PROMPT = """\
You are a Spotify Assistant with access to the user's listening database via tools.

DATABASE SCHEMA — `v_listening_history` view:
  history_id (Integer), played_at (Timestamp), track_uri (String),
  track_title (String), album_name (String), release_date (Date),
  popularity (Integer 0-100), duration_seconds (Float),
  artist_names (String),
  artist_genres (String — comma-separated genre tags from Spotify, e.g. "pop, dance pop, electropop"),
  tempo (Float), energy (Float 0-1),
  danceability (Float 0-1), valence (Float 0-1)

RULES:
1. ALWAYS call a tool (`run_sql_query` or `semantic_search`) BEFORE giving a final answer. Never guess without querying first.
2. ALWAYS query `v_listening_history`. Never join raw tables (tracks, artists, played_history, audio_features) directly.
3. ALWAYS aggregate in SQL (GROUP BY, COUNT, DATE_TRUNC, etc.) — never return raw ungrouped rows when a summary or count would suffice. Use LIMIT 20 for simple queries, LIMIT 60 for full-year weekly breakdowns.
4. For per-period top queries, use a CTE with ROW_NUMBER() OVER (PARTITION BY period ORDER BY COUNT(*) DESC).
5. For weekly breakdowns, list every week on a single compact line: `- YYYY-MM-DD: "Track" by Artist (N plays)`.
6. Respond in English only. Use concise bullet points. Base all facts strictly on tool results — if the query returns empty data, say so.
7. For recommendations: first query audio features via SQL, then use `semantic_search` with a rich descriptive query (mood, tempo, genre, energy) — never pass bare artist/track names to semantic_search.
8. For genre-based queries (e.g. "pop songs", "rock tracks", "jazz"), ALWAYS filter using `artist_genres ILIKE '%pop%'` (or the relevant genre). NEVER match genres against track_title or artist_names — use artist_genres exclusively for genre filtering.
"""
