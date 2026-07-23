from typing import Protocol

from src.models.track import Track


class VectorRepository(Protocol):
    def search_similar_lyrics(
        self, query_embedding: list[float], limit: int = 3
    ) -> list[dict]: ...

    def save_lyrics_vector(): ...


class TrackRepository(Protocol):
    def add(self, track: Track) -> None: ...

    def get_by_uri(self, uri: str) -> Track: ...
