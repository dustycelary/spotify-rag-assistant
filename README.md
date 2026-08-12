# Spotify RAG Assistant 🎵🤖

An agentic Retrieval-Augmented Generation (RAG) assistant for querying and analyzing your personal Spotify listening history, audio features, lyrics, and song embeddings.

It combines structured relational querying (SQL) with vector similarity search (`pgvector`) powered by a local Ollama LLM (`llama3.2` / `qwen2.5:7b`) and `sentence-transformers`.

---

## 🌟 Features

- **Natural Language to SQL**: Translates questions like *"What were my top listened songs last month?"* into SQL queries over `v_listening_history`.
- **Semantic Vector Search (RAG)**: Recommends tracks based on subjective vibe, mood, acoustic traits, or tempo using `pgvector` distance matching.
- **Audio Metric Insights**: Query tracks based on Spotify audio parameters including BPM (tempo), energy, danceability, and valence.
- **Agentic Function Calling**: Uses Ollama's tool-calling loop to autonomously choose between SQL lookup (`run_sql_query`) and vector search (`semantic_search`).

---

## 🛠 Tech Stack

- **Language**: Python 3.12+
- **LLM Engine**: [Ollama](https://ollama.ai/) (`llama3.2` or `qwen2.5:7b`)
- **Embedding Model**: `sentence-transformers` (e.g., `all-MiniLM-L6-v2`)
- **Database**: PostgreSQL 15 with `pgvector`
- **Database ORM**: SQLAlchemy 2.0 & `psycopg2-binary`
- **Spotify Integration**: `spotipy` (OAuth 2.0 PKCE / Spotify Web API)
- **Containerization**: Docker & Docker Compose

---

## 📂 Project Structure

```text
spotify-rag-assistant/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── main.py              # CLI interactive entry point & runtime loop
│   ├── agent_tools.py       # Ollama chat loop & tool execution handlers
│   ├── agent_context.py     # System prompt, DB schema layout & tool signatures
│   ├── db.py                # Database session initialization & schema creation
│   ├── helpers.py           # Spotify API synchronization & helper scripts
│   └── models/              # SQLAlchemy ORM models
│       ├── artist.py
│       ├── audio_features.py
│       ├── embedding.py
│       ├── lyrics.py
│       ├── played_history.py
│       └── track.py
```

## 🚀 Getting Started

### Prerequisites

1. Docker & Docker Compose installed.
2. Ollama installed and running locally on your machine.
ollama pull llama3.2

3. A Spotify Developer Account with a registered application to obtain Client ID & Client Secret.
──────

### Environment Setup

Create a .env file in the root directory and fill with values such as in [example](.env.example)

──────

### Installation & Running Locally

1. Start the Postgres + pgvector database container:
docker compose up -d db

2. Set up a Python virtual environment & install dependencies:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

3. Run the assistant CLI:
python -m src.main
