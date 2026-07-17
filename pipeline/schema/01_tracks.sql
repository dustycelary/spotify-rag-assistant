-- TODO: add all tables to schema (plan)
-- TODO: add a way to import spotify data

CREATE TABLE IF NOT EXISTS tracks (
        uri VARCHAR(50) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
	album_name VARCHAR(50) NOT NULL, 
	album_uri VARCHAR(50) NOT NULL, 
	release_date date NOT NULL,
	popularity integer, -- NOTE: how to represent this? 
	last_listened_to date NOT NULL, 
        artist VARCHAR(255) NOT NULL,
	duration_ms integer NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
