# Spotify RAG Assistant

An agentic Retrieval-Augmented Generation (RAG) assistant for querying and analyzing your personal Spotify listening history, audio features, lyrics, and song embeddings.

## Prerequisites

### Software

- **Language**: Python 3.11+
- **LLM Engine**: [Ollama](https://ollama.ai/)
- **Database**: PostgreSQL 15 with `pgvector`
- **Database ORM**: SQLAlchemy 2.0
- **Containerization**: Docker & Docker Compose

### API keys

- A [Spotify Developer Account](https://developer.spotify.com/)
- A [Genius Account](https://genius.com/) *(or API portal link)*

## Installation

1. Clone the repo

```bash
git clone git@github.com:dustycelary/spotify-rag-assistant.git && cd spotify-rag-assistant
```


2. Setup Python environment

```bash
python3 -m venv venv && source venv/bin/activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Download LLM model

```bash
ollama pull qwen2.5:14b
```

## Configuration

1. Copy template environment

```bash
cp .env.example .env
```

2. set `OLLAMA_MODEL` to your installed model. 

### Spotify Developer

1. Login to [Spotify Developer](https://developer.spotify.com/dashboard)
2. Create an app
3. Fill in details and set Redirect URI to redirect_uri value in [env](./.env)
4. Copy your Client ID and secret into [env](./.env) under `client_id` and `client_secret`

### Genius setup

1. Sign up to Genius lyrics API: [Genius](https://genius.com/api-clients)
2. Create an API client and set app website URL to `http://localhost`
3. Generate access token and copy it into [env](./.env) as GENIUS_ACCESS_TOKEN

## Importing Spotify history

This script:

1. Parses Spotify history `JSON` files and populates PostgreSQL database with it.
2. Adds audio metadata such as: BPM, energy, danceability and valence.
3. Generates embeddings for semantic searching.

### Downloading Spotify history

1. Go to [Spotify privacy settings](https://www.spotify.com/account/privacy/)
2. Request Extended streaming history.
3. Unzip file once processed and downloaded.

### Run import script

First ensure your database container is active using (`docker compose up -d db`), then run:

```bash
python src/import_spotify_history.py --path "/path/to/extended history"
```

### Script options

| Flag | Default | Behaviour |
| :-- | :-- | :-- |
| `--path <path>` | `playground/spotify_data/` | File or directory where spotify history is stored |
| `--reset` | false | Removes data from all existing database tables to start fresh with new data |

## Running assistant

> [!IMPORTANT]
> For app to work database must be filled with personal Spotify data. To do this refer to [Importing Spotify history](#importing-spotify-history)

1. Start the database container

```bash
docker compose up -d --remove-orphans db
```

1. Start Ollama

```bash
brew services run ollama
```

1. Run the app

```bash
python3 -m src.main
```

## Logging

Logs are always appended to `logs/app.log` at INFO level. To also display logs in the terminal, run:

```bash
python3 -m src.main --log-console
```

To follow the application logs:

```bash
tail -f logs/app.log
```

Application logs can contain personal questions and generated SQL. Review them before sharing. The import script writes its logs to the console, and log rotation is not configured.

PostgreSQL logs are managed separately by Docker. To follow them:

```bash
docker compose logs -f db
```
