from sqlalchemy.orm import Session

from src.models.track import Track
from src.repositories.interfaces import TrackRepository


class TracksRepository(TrackRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, track: Track) -> None:
        self.session.merge(track)
        self.session.commit()

    def get_by_uri(self, uri: str) -> Track:
        track = self.session.query(Track).filter(Track.uri == uri).first()
        return track
