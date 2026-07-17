CREATE TABLE IF NOT EXISTS audio_features (
	track_uri VARCHAR PRIMARY KEY, 
	valence FLOAT, 
	energy FLOAT, 
	danceability FLOAT, 
	tempo FLOAT, 
	acousticness FLOAT, 
	instrumentalness FLOAT, 
	liveness FLOAT, 
	loudness FLOAT, 
	speechiness FLOAT, 
	
	CONSTRAINT fk_track
		FOREIGN KEY (track_uri)
		REFERENCES tracks(uri)
		ON DELETE CASCADE
	); 


CREATE TABLE IF NOT EXISTS lyrics (
	track_uri VARCHAR PRIMARY KEY, 
	raw_lyrics TEXT, 
	cleaned_lyrics TEXT, 
	song_description TEXT,
	genius_id integer, 
	updated_at timestamp,
	
	CONSTRAINT fk_track
		FOREIGN KEY (track_uri)
		REFERENCES tracks(uri)
	ON DELETE CASCADE -- TODO: is this the right ON DELETE TO USE? 
	); 



CREATE TABLE IF NOT EXISTS recently_played(
	id integer PRIMARY KEY, 
	track_uri varchar, -- can only be referernced once in this table 
	played_at timestamp, 
	-- context_type VARCHAR(255), 
	context_uri VARCHAR(255), 
	inserted_at timestamp,

	CONSTRAINT fk_track
		FOREIGN KEY (track_uri)
		REFERENCES tracks(uri)
	ON DELETE CASCADE
);
