CREATE EXTENSION IF NOT EXISTS vector; -- usedc pgvector over chromadb as it fits iwth existing database

-- embeddings table; for semantic lyric data 
CREATE TABLE IF NOT EXISTS embeddings (
    track_uri VARCHAR(255) PRIMARY KEY REFERENCES tracks(uri) ON DELETE CASCADE,
embedding VECTOR(384), -- for model all-MiniLM-L6-v2
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx 
ON embeddings USING hnsw (embedding vector_cosine_ops); -- cosine distance to judge similarity of track lyrics
