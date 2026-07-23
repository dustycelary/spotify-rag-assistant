from src.db import SessionLocal
from src.models.embedding import Embedding
from src.models.lyrics import Lyrics
from src.models.track import Track
from src.rag import embed_text

"""Tools available to agent for query routing using Agentic Tooling"""
# TODO: add these
"""
  • get_current_top_artists(time_range="short_term")
      • Why: If the user asks "What am I obsessed with right now?", the AI can hit the Spotify API to get their current listening trends, rather than relying on stale database data.
  • recommend_similar_songs(seed_track_name)
      • Why: The AI can use Spotify's actual recommendation algorithm to generate playlists on the fly based on a specific song the user likes.
  • create_themed_playlist(playlist_name, list_of_track_uris)
      • Why: This gives your AI "write" access to Spotify! The user can say "Make me a playlist of sad songs about rain", the AI queries your local pgvector database for matching
      lyrics, grabs the track URIs, and uses this tool to instantly create a real, playable playlist in the user's Spotify account!
  • get_artist_genres(artist_name)
      • Why: Useful if the user asks "What kind of music does Glass Animals make?" The AI can fetch the official genres straight from the Spotify API.
"""


def ai_available(func):
    """Decorator to mark functions available to AI model"""
    func.is_available = True
    return func


class AgentTools:
    """Centralising all tools available to agent"""

    @ai_available
    def search_lyrics_by_keyword(self, keyword: str, limit: int = 3) -> list[dict]:
        """Performs a semantic vector search on song lyrics in pgvector for a given theme or topic.

        Args:
            theme: The abstract theme, emotion, or lyric phrase to search for (e.g. 'heartbreak', 'driving in rain').
            limit: Maximum number of tracks to return.
        """

        keyword_vector = embed_text(keyword)
        similar_tracks = self.search_similar_lyrics(keyword_vector, limit)

        return similar_tracks

    def search_lyrics_by_embedding(
        self, query_embedding: list[float], limit: int = 3
    ) -> list[dict]:
        results = {}
        with SessionLocal() as session:
            results = (
                self.session.query(Track, Lyrics, Embedding)
                .join(Embedding, Track.uri == Embedding.track_uri)
                .join(Lyrics, Track.uri == Lyrics.track_uri)
                .order_by(Embedding.embedding.cosine_distance(query_embedding))
                .limit(limit)
                .all()
            )

        return [
            {
                "uri": track.uri,
                "title": track.title,
                "artist": track.artist,
                "cleaned_lyrics": lyrics.cleaned_lyrics,
            }
            for track, lyrics, embedding in results
        ]

    @ai_available
    def get_listening_history(
        self, artist: str | None = None, days: int = 7, limit: int = 10
    ) -> list[dict]:
        """Queries user's SQL listening history from PostgreSQL.

        Args:
            artist: Optional artist name filter.
            days: Lookback window in days (default 7).
            limit: Max records.
        """
        # Execute SQL query on recently_played and tracks tables
        return [{}]

    @ai_available
    def query_audio_features(
        self,
        min_energy: float | None = None,
        min_valence: float | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Queries numerical audio features (danceability, energy, tempo, valence) from SQL.

        Args:
            min_energy: Minimum energy value (0.0 to 1.0).
            min_valence: Minimum valence/happiness value (0.0 to 1.0).
            limit: Max records.
        """

        # Execute SQL query on audio_features table

        return [{}]
