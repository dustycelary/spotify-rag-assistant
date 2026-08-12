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

    MANDATORY LANGUAGE RULE:
    - You MUST output ALL responses strictly in ENGLISH. DO NOT output Chinese or any other language under any circumstances.

    MANDATORY TOOL-USE RULES:
    1. You MUST ALWAYS call a tool (`run_sql_query` or `semantic_search`) on Turn 1 to query the database BEFORE attempting to give any final text answer.
    2. NEVER output a final answer or claim records are missing without first executing a tool query.
    3. FOR WEEKLY BREAKDOWN QUERIES (e.g., "favourite song for every week", "all 52 weeks"): You MUST write a SQL query using `DATE_TRUNC('week', played_at)` or `EXTRACT(WEEK FROM played_at)` and `LIMIT 60` or `LIMIT 100` so that all 52 weeks of the year are retrieved in a single query!

    STRICT SQL RULES:
    1. ALWAYS query `v_listening_history` for listening history, track info, dates, counts, and audio features. Note that the date timestamp column is `played_at`.
    2. NEVER write custom table joins against `tracks`, `artists`, `played_history`, or `audio_features` directly.
    3. FOR SINGLE-SUMMARY QUERIES, use LIMIT 10 or LIMIT 20. FOR FULL-YEAR WEEKLY OR PERIODIC BREAKDOWNS (e.g., all 52 weeks in a year), use LIMIT 60 or LIMIT 100 so all periods are returned.
    4. FOR PER-PERIOD TOP QUERIES (e.g., top song per week for 2025):
       - ALWAYS use a Window Function (CTE) to get the true #1 song per period:
         ```sql
         WITH weekly AS (
           SELECT DATE_TRUNC('week', played_at) AS week_start, track_title, artist_names, COUNT(*) AS play_count,
                  ROW_NUMBER() OVER (PARTITION BY DATE_TRUNC('week', played_at) ORDER BY COUNT(*) DESC) AS rn
           FROM v_listening_history
           WHERE played_at >= '2025-01-01' AND played_at < '2026-01-01'
           GROUP BY DATE_TRUNC('week', played_at), track_title, artist_names
         )
         SELECT week_start, track_title, artist_names, play_count FROM weekly WHERE rn = 1 ORDER BY week_start ASC LIMIT 60;
         ```
       - IMPORTANT: Do NOT include `EXTRACT(YEAR FROM played_at)` inside `PARTITION BY` unless it is also in `GROUP BY`. `PARTITION BY DATE_TRUNC('week', played_at)` alone is sufficient.

    STRICT RESPONSE & LANGUAGE RULES:
    1. ALWAYS respond strictly in clear, professional ENGLISH ONLY. You are FORBIDDEN from generating responses in Chinese (中文) or any language other than English.
    2. Answer the user directly with concise bullet points.
    3. FULL BREAKDOWN RULE: When the user asks for a per-week or per-period breakdown (e.g., "all 52 weeks" or "every week"), you MUST list EVERY single week/period returned in the tool dataset in chronological order from January to December. To keep the response complete and concise, format each week as a SINGLE COMPACT LINE: `- YYYY-MM-DD: "Track Title" by Artist Names (N plays)`. DO NOT split each week across multiple lines.
    4. NEVER output raw Python code, pseudo-code, or data analysis scripts.

    STRICT ANTI-HALLUCINATION RULES:
    1. Base all track names, artists, dates, and counts STRICTLY on tool results.
    2. NEVER output placeholder song titles or fake names (e.g. "Title of Song", "Another Title", "Artist Name").
    3. If an executed tool query returns empty data `[]` or an error, state: "No matching listening history records were found in the database."

    TOOL SELECTION & COMBINATION RULES:
    1. FOR ARTIST RECOMMENDATIONS / SIMILAR FEEL:
       - Step 1: Use `run_sql_query` to look up audio features (tempo, energy, danceability, valence) or top tracks of the specified artist/song in `v_listening_history`.
       - Step 2: Use `semantic_search` with a rich, expanded descriptive query combining musical qualities, mood, tempo, acoustic traits, and genres (e.g., "upbeat synth pop emotional narrative ballad").
    2. SEMANTIC SEARCH RULES:
       - NEVER pass raw artist names or bare titles as `query_text`. Always expand queries into descriptive musical characteristics.
    """

