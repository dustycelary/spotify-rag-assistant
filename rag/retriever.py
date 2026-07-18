import psycopg2


class Retriever:
    """Retrieves tracks and lyrics from the database using semantic search.

    It connects to postgresql and uses pgvector queries to calculate
    similarity between query embeddings."""

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn

    def search_similar_lyrics(
        self, query_embedding: list[float], limit: int = 3
    ) -> list[dict]:
        """Fetch songs with similar lyrics
        Args:
            query_embedding: Vector for the original track
            limit: number of similar tracks to return

        Returns:
            List[Dict]: with keys (uri, title, artist, cleaned_lyrics, similarity)"""

        query = """
            SELECT 
                t.uri, 
                t.title, 
                t.artist, 
                l.cleaned_lyrics,
                1 - (e.embedding <=> %s::vector) AS similarity_score
            FROM embeddings e
            JOIN tracks t ON e.track_uri = t.uri
            JOIN lyrics l ON l.track_uri = t.uri
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (query_embedding, query_embedding, limit))
            rows = cur.fetchall()
            return [
                {
                    "uri": r[0],
                    "title": r[1],
                    "artist": r[2],
                    "cleaned_lyrics": r[3],
                    "similarity": r[4],
                }
                for r in rows
            ]
