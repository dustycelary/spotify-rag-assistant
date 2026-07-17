CREATE TABLE if not exists artists(
	uri VARCHAR(50) PRIMARY KEY, 
	name VARCHAR(255) NOT NULL, 
	genres VARCHAR[], 
	popularity integer, 
	updated_at timestamp

	CONSTRAINT fk_track_artists
		FOREIGN KEY (track_uri)
		REFERENCES tracks(uri)
	ON DELETE 
)
