CREATE TABLE IF NOT EXISTS track_artists (
	track_uri VARCHAR(50), 
	artist_uri VARCHAR(50),
	PRIMARY KEY (track_uri, artist_uri), 
	CONSTRAINT fk_track FOREIGN KEY
	CONSTRAINT fk_artist FOREIGN KEY
)
