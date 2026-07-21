CREATE TABLE IF NOT EXISTS tracks (
    uri VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    album_name VARCHAR(255),
    album_uri VARCHAR(255),
    release_date DATE,
    popularity INTEGER,
    duration_ms INTEGER,
    artist VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
