from sqlalchemy.orm import Session

from src.models.embedding import Embedding
from src.models.lyrics import Lyrics
from src.models.track import Track
from src.repositories.interfaces import VectorRepository


class PgVectorRepository(VectorRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def search_similar_lyrics(
        self, query_embedding: list[float], limit: int = 3
    ) -> list[dict]:
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

    def save_lyrics_vector(self):
        # TODO: implement save_lyrics_vector function
        pass
