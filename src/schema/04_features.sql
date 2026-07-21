
-- Audio Features Table (1-to-1 with tracks)
CREATE TABLE IF NOT EXISTS audio_features (
    track_uri VARCHAR(255) PRIMARY KEY REFERENCES tracks(uri) ON DELETE CASCADE,
    valence REAL,
    energy REAL,
    danceability REAL,
    tempo REAL,
    acousticness REAL,
    instrumentalness REAL,
    liveness REAL,
    loudness REAL,
    speechiness REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lyrics and Metadata Table
CREATE TABLE IF NOT EXISTS lyrics (
    track_uri VARCHAR(255) PRIMARY KEY REFERENCES tracks(uri) ON DELETE CASCADE,
    raw_lyrics TEXT,
    cleaned_lyrics TEXT,
    song_description TEXT, -- Rich context from Genius
    genius_id INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recently Played Log
CREATE TABLE IF NOT EXISTS recently_played (
    id SERIAL PRIMARY KEY,
    track_uri VARCHAR(255) REFERENCES tracks(uri) ON DELETE CASCADE,
    played_at TIMESTAMP WITH TIME ZONE NOT NULL,
    context_type VARCHAR(50), -- e.g., 'playlist', 'album', 'artist'
    context_uri VARCHAR(255),
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_play UNIQUE (track_uri, played_at) -- Prevents duplicate entries on overlap
);

