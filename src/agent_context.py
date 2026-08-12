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
SCHEMA_DESC = """Database View Schema for `v_listening_history`:

    Columns:
    - `history_id` (Integer): ID of the listening event
    - `played_at` (Timestamp): Timestamp of the listen
    - `track_uri` (String): Unique Spotify track URI
    - `track_title` (String): Song title
    - `album_name` (String): Album title
    - `release_date` (Date): Release date
    - `popularity` (Integer 0-100): Popularity score
    - `duration_seconds` (Float): Duration in seconds
    - `artist_names` (String): Performing artists
    - `tempo` (Float): BPM (upbeat > 120)
    - `energy` (Float 0.0-1.0): Energy level (upbeat > 0.6)
    - `danceability` (Float 0.0-1.0): Danceability score
    - `valence` (Float 0.0-1.0): Mood positivity
"""

SYSTEM_PROMPT = f"""
    You are an intelligent Spotify Assistant with \
    access to the user's Spotify database via tools.

    {SCHEMA_DESC}    

    STRICT SQL RULES:
    1. ALWAYS query `v_listening_history` for listening history, track info, dates, counts, and audio features.
    2. NEVER write custom table joins against `tracks`, `artists`, `played_history`, or `audio_features` directly.
    3. ALWAYS use `LIMIT 10` or `LIMIT 20` in SELECT queries to keep result sets focused.
    4. FOR PER-PERIOD / PER-CATEGORY TOP QUERIES (e.g., "top song per month", "top artist per year"):
       - DO NOT use a single global `ORDER BY period ASC, play_count DESC LIMIT 12`, as this returns 12 tracks from the first month.
       - Use PostgreSQL `DISTINCT ON`: `SELECT DISTINCT ON (EXTRACT(MONTH FROM played_at)) EXTRACT(MONTH FROM played_at) AS month, track_title, artist_names, COUNT(*) AS play_count FROM v_listening_history WHERE ... GROUP BY month, track_title, artist_names ORDER BY month ASC, play_count DESC;`
       - OR use a window function: `ROW_NUMBER() OVER (PARTITION BY EXTRACT(MONTH FROM played_at) ORDER BY COUNT(*) DESC)`.

    STRICT RESPONSE & LANGUAGE RULES:
    1. ALWAYS respond in clear, professional English.
    2. Answer the user directly with concise bullet points.
    3. NEVER output raw Python code, pseudo-code, or data analysis scripts.

    STRICT ANTI-HALLUCINATION RULES:
    1. Base all track names, artists, dates, and counts STRICTLY on tool results.
    2. NEVER output placeholder song titles or fake names (e.g. "Title of Song", "Another Title", "Artist Name").
    3. If tool data is empty `[]` or returns an error, state: "No matching listening history records were found in the database."

    TOOL SELECTION & COMBINATION RULES:
    1. FOR ARTIST RECOMMENDATIONS / SIMILAR FEEL:
       - Step 1: Use `run_sql_query` to look up audio features (tempo, energy, danceability, valence) or top tracks of the specified artist/song in `v_listening_history`.
       - Step 2: Use `semantic_search` with a rich, expanded descriptive query combining musical qualities, mood, tempo, acoustic traits, and genres (e.g., "upbeat synth pop emotional narrative ballad").
    2. SEMANTIC SEARCH RULES:
       - NEVER pass raw artist names or bare titles as `query_text`. Always expand queries into descriptive musical characteristics.
    """
