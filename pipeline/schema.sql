CREATE TABLE IF NOT EXISTS tracks (
        id VARCHAR(50) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        artist VARCHAR(255) NOT NULL,
        lyrics TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

