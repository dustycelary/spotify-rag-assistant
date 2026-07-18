CREATE TABLE IF NOT EXISTS track_artists (
    track_uri VARCHAR(255) REFERENCES tracks(uri) ON DELETE CASCADE,
    artist_uri VARCHAR(255) REFERENCES artists(uri) ON DELETE CASCADE,
    PRIMARY KEY (track_uri, artist_uri)
);
