# PostgreSQL Database Export: `spotify_rag`

## 1. Database Schema

### Table: `artists`
| Column Name | Data Type | Nullable |
| --- | --- | --- |
| `uri` | `character varying` | NO |
| `name` | `character varying` | NO |
| `genres` | `ARRAY` | YES |
| `popularity` | `integer` | YES |
| `updated_at` | `timestamp without time zone` | YES |


### Table: `audio_features`
| Column Name | Data Type | Nullable |
| --- | --- | --- |
| `track_uri` | `character varying` | NO |
| `valence` | `double precision` | YES |
| `energy` | `double precision` | YES |
| `danceability` | `double precision` | YES |
| `tempo` | `double precision` | YES |
| `acousticness` | `double precision` | YES |
| `instrumentalness` | `double precision` | YES |
| `liveness` | `double precision` | YES |
| `loudness` | `double precision` | YES |
| `speechiness` | `double precision` | YES |
| `updated_at` | `timestamp without time zone` | YES |


### Table: `embeddings`
| Column Name | Data Type | Nullable |
| --- | --- | --- |
| `track_uri` | `character varying` | NO |
| `embedding` | `USER-DEFINED` | YES |
| `updated_at` | `timestamp without time zone` | YES |


### Table: `lyrics`
| Column Name | Data Type | Nullable |
| --- | --- | --- |
| `track_uri` | `character varying` | NO |
| `raw_lyrics` | `text` | YES |
| `cleaned_lyrics` | `text` | YES |
| `song_description` | `text` | YES |
| `genius_id` | `integer` | YES |
| `updated_at` | `timestamp without time zone` | YES |


### Table: `track_artists`
| Column Name | Data Type | Nullable |
| --- | --- | --- |
| `track_uri` | `character varying` | NO |
| `artist_uri` | `character varying` | NO |


### Table: `tracks`
| Column Name | Data Type | Nullable |
| --- | --- | --- |
| `uri` | `character varying` | NO |
| `title` | `character varying` | NO |
| `album_name` | `character varying` | YES |
| `album_uri` | `character varying` | YES |
| `release_date` | `date` | YES |
| `popularity` | `integer` | YES |
| `duration_ms` | `integer` | YES |
| `artist` | `character varying` | YES |
| `updated_at` | `timestamp without time zone` | YES |


## 2. Current Database Contents

### Table: `artists`
**Total rows:** `0`

*Table is currently empty.*

### Table: `audio_features`
**Total rows:** `0`

*Table is currently empty.*

### Table: `embeddings`
**Total rows:** `0`

*Table is currently empty.*

### Table: `lyrics`
**Total rows:** `0`

*Table is currently empty.*

### Table: `track_artists`
**Total rows:** `0`

*Table is currently empty.*

### Table: `tracks`
**Total rows:** `0`

*Table is currently empty.*
