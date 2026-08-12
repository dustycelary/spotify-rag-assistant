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
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "llama3.2")
logger = logging.getLogger(__name__)
MAX_TOOL_TURNS = int(os.environ.get("MAX_TOOL_TURNS", "6"))

OLLAMA_OPTIONS = {"temperature": 0.1, "num_predict": 2048, "num_ctx": 8192}
NO_TOOL_RECOVERY = (
    "Before answering this Spotify-data request, call the appropriate tool. Use "
    "`run_sql_query` for listening-history facts, dates, counts, rankings, metadata, "
    "genres, or audio features. Use `semantic_search` for subjective discovery from "
    "qualities the user supplied. For similarity to a named track, retrieve that "
    "track with SQL first. Do not provide a factual final answer yet."
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
                    messages.append({"role": "assistant", "content": content})
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

            messages.append(msg)
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
                    payload = {
                        "status": "error",
                        "error": {
                            "code": "invalid_arguments",
                            "message": (
                                "Tool arguments must be a JSON object. Correct the "
                                "call and retry."
                            ),
                        },
                    }
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": json.dumps(payload, separators=(",", ":")),
                        }
                    )
                    continue

                encoded_args = json.dumps(func_args, sort_keys=True, default=str)
                signature = f"{func_name}:{encoded_args}"
                if signature in seen_tool_calls:
                    payload = {
                        "status": "error",
                        "error": {
                            "code": "duplicate_call",
                            "message": (
                                "This exact tool call already ran. Use its earlier "
                                "result or change the call."
                            ),
                        },
                    }
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": json.dumps(payload, separators=(",", ":")),
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
                        payload = {
                            "status": "error",
                            "error": {
                                "code": "unknown_tool",
                                "message": (
                                    f"Unknown tool `{func_name}`. Use one of the "
                                    "provided tools."
                                ),
                            },
                        }
                        messages.append(
                            {
                                "role": "tool",
                                "tool_name": func_name,
                                "content": json.dumps(payload, separators=(",", ":")),
                            }
                        )
                        continue
                except ValueError as exc:
                    logger.warning("Rejected tool call on Turn %d: %s", turn, exc)
                    payload = {
                        "status": "error",
                        "error": {"code": "invalid_request", "message": str(exc)},
                    }
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": json.dumps(payload, separators=(",", ":")),
                        }
                    )
                    continue
                except Exception:
                    logger.exception("Tool execution failed on Turn %d", turn)
                    session.rollback()
                    code = (
                        "sql_execution_error"
                        if func_name == "run_sql_query"
                        else "semantic_search_error"
                    )
                    message = (
                        "The query failed. Rewrite it using only documented "
                        "columns from v_listening_history."
                        if func_name == "run_sql_query"
                        else "Semantic search failed. Retry or explain that "
                        "recommendations are unavailable."
                    )
                    payload = {
                        "status": "error",
                        "error": {"code": code, "message": message},
                    }
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": func_name,
                            "content": json.dumps(payload, separators=(",", ":")),
                        }
                    )
                    continue

                successful_tool_calls += 1
                payload = {
                    "status": "ok",
                    "row_count": len(rows),
                    "rows": rows,
                }
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
                        "content": json.dumps(
                            payload, default=str, separators=(",", ":")
                        ),
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
    result = connection.exec_driver_sql(sql)
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
