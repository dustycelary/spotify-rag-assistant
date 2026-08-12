import json
import logging
import os
import re
from datetime import datetime
from typing import Any

import dotenv
import ollama
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.agent_context import TOOLS, build_system_prompt
from src.models.embedding import Embedding
from src.models.track import Track

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


MODEL_NAME = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
MAX_TOOL_TURNS = int(os.environ.get("MAX_TOOL_TURNS", "4"))

OLLAMA_OPTIONS = {
    "temperature": 0.1,
    "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "4096")),
    "num_predict": int(os.environ.get("OLLAMA_NUM_PREDICT", "768")),
}

NO_TOOL_RECOVERY = (
    "Call a tool before answering: SQL for facts; semantic search for "
    "user-supplied musical qualities. For named-track similarity, use SQL first."
)

FORBIDDEN_RELATIONS = {
    "artists",
    "audio_features",
    "embeddings",
    "lyrics",
    "played_history",
    "tracks",
    "track_artists",
}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def answer_question(question: str, session: Session, embed_model) -> str:
    messages: list[Any] = [
        {
            "role": "system",
            "content": build_system_prompt(datetime.now().astimezone()),
        },
        {"role": "user", "content": question},
    ]
    total_tool_calls = 0
    successful_tool_calls = 0
    seen_tool_calls: set[str] = set()

    logger.info("=" * 60)
    logger.info("NEW QUERY: %s", question)
    logger.info("=" * 60)

    try:
        for turn in range(1, MAX_TOOL_TURNS + 1):
            logger.info("Agent Turn %d/%d: Prompting model...", turn, MAX_TOOL_TURNS)
            response = ollama.chat(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                options=OLLAMA_OPTIONS,
                keep_alive=OLLAMA_KEEP_ALIVE,
            )
            msg = _field(response, "message")
            if not msg:
                return "No response could be generated."

            logger.info("Agent Turn %d/%d message: [%s]", turn, MAX_TOOL_TURNS, msg)
            tool_calls = _field(msg, "tool_calls")

            if not tool_calls:
                content = _field(msg, "content", "") or ""
                if successful_tool_calls == 0:
                    logger.warning(
                        "Turn %d provided no answerable tool evidence; "
                        "requesting a tool call.",
                        turn,
                    )
                    messages.append({"role": "assistant", "content": ""})
                    messages.append({"role": "user", "content": NO_TOOL_RECOVERY})
                    continue

                logger.info(
                    "Agent completed at Turn %d/%d after %d call(s), %d successful.",
                    turn,
                    MAX_TOOL_TURNS,
                    total_tool_calls,
                    successful_tool_calls,
                )
                return content or "No response could be generated."

            # Keep the tool calls but discard prose the model generated alongside
            # them; it adds tokens without helping the next turn.
            messages.append(
                {"role": "assistant", "content": "", "tool_calls": tool_calls}
            )
            for tool_call in tool_calls:
                total_tool_calls += 1
                func_info = _field(tool_call, "function", {})
                func_name = _field(func_info, "name")
                raw_args = _field(func_info, "arguments", {})

                try:
                    func_args = (
                        json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    )
                    if not isinstance(func_args, dict):
                        raise ValueError
                except (json.JSONDecodeError, ValueError, TypeError):
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": '{"error":"Use valid JSON arguments."}',
                        }
                    )
                    continue

                encoded_args = json.dumps(func_args, sort_keys=True, default=str)
                signature = f"{func_name}:{encoded_args}"
                if signature in seen_tool_calls:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": '{"error":"Duplicate call; use prior result."}',
                        }
                    )
                    continue
                seen_tool_calls.add(signature)

                logger.info(
                    "Agent Turn %d tool call #%d: %s",
                    turn,
                    total_tool_calls,
                    signature,
                )
                try:
                    if func_name == "run_sql_query":
                        sql_arg = func_args.get("sql")
                        if not isinstance(sql_arg, str) or not sql_arg.strip():
                            raise ValueError("The required `sql` argument is missing.")
                        rows = run_structured_query(sql_arg, session)
                    elif func_name == "semantic_search":
                        query_text = func_args.get("query_text")
                        if not isinstance(query_text, str) or not query_text.strip():
                            raise ValueError(
                                "The required `query_text` argument is missing."
                            )
                        embedding = embed_question(query_text, embed_model)
                        rows = semantic_search(embedding, session)
                    else:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_name": func_name,
                                "content": '{"error":"Unknown tool."}',
                            }
                        )
                        continue
                except ValueError as exc:
                    logger.warning("Rejected tool call on Turn %d: %s", turn, exc)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": json.dumps(
                                {"error": str(exc)}, separators=(",", ":")
                            ),
                        }
                    )
                    continue
                except Exception:
                    logger.exception("Tool execution failed on Turn %d", turn)
                    session.rollback()
                    message = (
                        "Query failed; retry with documented view columns."
                        if func_name == "run_sql_query"
                        else "Search failed; retry or report it unavailable."
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": json.dumps(
                                {"error": message}, separators=(",", ":")
                            ),
                        }
                    )
                    continue

                successful_tool_calls += 1
                logger.info(
                    "Agent Turn %d tool #%d returned %d row(s)",
                    turn,
                    total_tool_calls,
                    len(rows),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": func_name,
                        "content": json.dumps(rows, default=str, separators=(",", ":")),
                    }
                )

        return "I couldn't complete the request within the available tool turns."
    except Exception:
        logger.exception("Ollama agent error")
        return "Sorry, I couldn't process that query due to an agent service error."


def clean_sql(raw: str) -> str:
    sql = re.sub(r"^\s*```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```\s*$", "", sql).strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


def validate_sql(sql: str) -> str:
    """Apply narrow structural checks before PostgreSQL's read-only enforcement."""
    if not sql:
        raise ValueError("SQL cannot be empty.")

    without_comments = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.DOTALL)
    # Mask quoted string contents so titles such as "Delete Me" and literal
    # semicolons are not mistaken for SQL syntax.
    structural_sql = re.sub(r"'(?:''|[^'])*'", "''", without_comments)
    if ";" in structural_sql:
        raise ValueError("Only one SQL statement is allowed.")
    normalized = structural_sql.strip().lower()
    if not re.match(r"^(select|with)\b", normalized):
        raise ValueError("Only SELECT or WITH ... SELECT statements are allowed.")
    if re.search(
        r"\b(insert|update|delete|merge|drop|alter|create|truncate)\b", normalized
    ):
        raise ValueError("Data-changing SQL is not allowed.")
    if not re.search(r"\bv_listening_history\b", normalized):
        raise ValueError("Queries must reference v_listening_history.")

    identifiers = set(re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", normalized))
    forbidden = sorted(identifiers & FORBIDDEN_RELATIONS)
    if forbidden:
        raise ValueError(
            "Raw tables are unavailable; query only v_listening_history "
            f"(found: {', '.join(forbidden)})."
        )
    return sql


def run_structured_query(
    sql: str, session: Session, max_rows: int = 100, timeout_ms: int = 5000
) -> list[dict]:
    """Validate and execute one read-only SQL query, returning plain rows."""
    sql = validate_sql(clean_sql(sql))
    connection = session.connection()
    connection.exec_driver_sql(f"SET LOCAL statement_timeout = '{int(timeout_ms)}ms'")
    connection.exec_driver_sql("SET LOCAL default_transaction_read_only = ON")
    # psycopg2 uses percent-based parameter markers even when no parameters are
    # supplied. Escape lone wildcard characters before sending raw driver SQL;
    # validation and any caller logging intentionally retain the readable SQL.
    driver_sql = re.sub(r"(?<!%)%(?!%)", "%%", sql)
    result = connection.exec_driver_sql(driver_sql)
    return [dict(row) for row in result.mappings().fetchmany(max_rows)]


def semantic_search(
    embedding: list[float], session: Session, k: int = 10
) -> list[dict]:
    distance = Embedding.embedding.cosine_distance(embedding).label("distance")
    stmt = (
        select(Embedding, distance)
        .options(
            joinedload(Embedding.track).selectinload(Track.artists),
            joinedload(Embedding.track).joinedload(Track.audio_features),
        )
        .order_by(distance)
        .limit(k)
    )
    results = session.execute(stmt).unique().all()

    rows = []
    for embedding_row, distance_value in results:
        track = embedding_row.track
        features = track.audio_features
        genres = sorted(
            {genre for artist in track.artists for genre in (artist.genres or [])}
        )
        rows.append(
            {
                "track_uri": track.uri,
                "track": track.title,
                "album": track.album_name,
                "artists": [artist.name for artist in track.artists],
                "artist_genres": genres,
                "release_date": str(track.release_date) if track.release_date else None,
                "popularity": track.popularity,
                "tempo": features.tempo if features else None,
                "energy": features.energy if features else None,
                "danceability": features.danceability if features else None,
                "valence": features.valence if features else None,
                "cosine_distance": float(distance_value),
            }
        )
    return rows


def embed_question(question: str, embed_model) -> list[float]:
    return embed_model.encode(question).tolist()
