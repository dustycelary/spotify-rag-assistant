import json
import logging
import os

import dotenv
import ollama
from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from src.agent_context import SYSTEM_PROMPT, TOOLS
from src.models.embedding import Embedding
from src.models.track import Track

dotenv.load_dotenv()
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "llama3.2")
logger = logging.getLogger(__name__)
MAX_TOOL_TURNS = int(os.environ.get("MAX_TOOL_TURNS"))


def answer_question(
    question: str, session: Session, embed_model, schema_desc: str = ""
) -> str:

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    total_tool_calls = 0

    try:
        for turn in range(1, MAX_TOOL_TURNS + 1):
            logger.info("Agent Turn %d/%d: Prompting model...", turn, MAX_TOOL_TURNS)
            response = ollama.chat(model=MODEL_NAME, messages=messages, tools=TOOLS)
            # msg = response.get("message") if response else None
            msg = getattr(response, "message", None)
            if not msg:
                return "No response could be generated."

            logger.info("Agent Turn %d/%d message: [%s]\n", turn, MAX_TOOL_TURNS, msg)
            tool_calls = getattr(msg, "tool_calls", None)

            if not tool_calls:
                content = getattr(msg, "content", None)

                logger.info(
                    "Agent completed reasoning at Turn %d/%d after %d tool call(s).",
                    turn,
                    MAX_TOOL_TURNS,
                    total_tool_calls,
                )
                return (
                    content or "No response could be generated."
                )  # ending ai tool turns

            messages.append(msg)
            for tool_call in tool_calls:
                total_tool_calls += 1
                func_info = getattr(tool_call, "function", {})
                func_name = getattr(func_info, "name", None)
                func_args = getattr(func_info, "arguments", {})

                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except Exception:
                        func_args = {}

                call_signature = (
                    f"{func_name}:{json.dumps(func_args, sort_keys=True, default=str)}"
                )
                logger.info(
                    "Agent Turn %d/%d [Call Signature:  #%s]:\n",
                    turn,
                    MAX_TOOL_TURNS,
                    call_signature,
                )

                data = []

                if func_name == "run_sql_query":
                    sql = clean_sql(func_args.get("sql", ""))
                    logger.info(
                        "Agent Turn %d/%d [Tool Call #%d - run_sql_query]:\n%s",
                        turn,
                        MAX_TOOL_TURNS,
                        total_tool_calls,
                        sql,
                    )
                    try:
                        data = run_structured_query(sql, session)
                    except Exception as e:
                        logger.error("SQL Execution Error on Turn %d: %s", turn, e)
                        session.rollback()
                        data = [
                            {
                                "error": (
                                    f"SQL Execution Error: {e}. "
                                    "Please rewrite the SQL query using columns from v_listening_history."
                                )
                            }
                        ]
                elif func_name == "semantic_search":
                    query_text = func_args.get("query_text", question)
                    logger.info(
                        "Agent Turn %d/%d [Tool Call #%d - semantic_search]: %s",
                        turn,
                        MAX_TOOL_TURNS,
                        total_tool_calls,
                        query_text,
                    )
                    try:
                        emb = embed_question(query_text, embed_model)
                        data = semantic_search(emb, session)
                    except Exception as e:
                        logger.error("Semantic Search Error on Turn %d: %s", turn, e)
                        session.rollback()
                        data = [{"error": f"Semantic Search Error: {e}"}]

                logger.info(
                    "Agent Turn %d/%d: Tool #%d execution returned %d item(s)",
                    turn,
                    MAX_TOOL_TURNS,
                    total_tool_calls,
                    len(data),
                )
                tool_msg_content = str(data)

                if not data:
                    tool_msg_content += (
                        " (No matching records in database for this request.)"
                    )

                messages.append({"role": "tool", "content": tool_msg_content})

        return "Could not finish as too many tool calls have been made"

    except Exception as e:
        logger.error(f"Ollama agent error: {e}")
        return f"Sorry, I couldn't process that query: {e}"


def run_structured_query(sql: str, session: Session, max_rows: int = 20) -> list[dict]:
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT statements allowed")
    result = session.execute(text(sql))
    return [dict(r) for r in result.mappings().fetchmany(max_rows)]


def semantic_search(
    embedding: list[float], session: Session, k: int = 10
) -> list[dict]:
    stmt = (
        select(Embedding)
        .options(joinedload(Embedding.track).selectinload(Track.artists))
        .order_by(Embedding.embedding.cosine_distance(embedding))
        .limit(k)
    )
    results = session.execute(stmt).unique().scalars().all()

    return [
        {
            "track": e.track.title,
            "album": e.track.album_name,
            "artists": [a.name for a in e.track.artists],
            "release_date": str(e.track.release_date) if e.track.release_date else None,
            "popularity": e.track.popularity,
        }
        for e in results
    ]


def clean_sql(raw: str) -> str:
    sql = raw.replace("```sql", "").replace("```", "").strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


def embed_question(question: str, embed_model) -> list[float]:
    return embed_model.encode(question).tolist()
