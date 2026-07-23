from src.rag import embed_text
from src.repositories.vector_repository import PgVectorRepository

"""Tools available to agent for query routing using Agentic Tooling"""


def ai_available(func):
    """Decorator to mark functions available to AI model"""
    func.is_available = True
    return func


class SpotifyTools:
    """Centralising all tools available to agent"""

    def __init__(self, db_conn):
        self.conn = db_conn

    @ai_available
    def search_lyrics_by_theme(self, theme: str, limit: int = 3) -> list[dict]:
        """Performs a semantic vector search on song lyrics in pgvector for a given theme or topic.

        Args:
            theme: The abstract theme, emotion, or lyric phrase to search for (e.g. 'heartbreak', 'driving in rain').
            limit: Maximum number of tracks to return.
        """

        theme_vector = embed_text(theme)
        db_retriever = PgVectorRepository(self.conn)
        similar_tracks = db_retriever.search_similar_lyrics(theme_vector, limit)

        return similar_tracks

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
