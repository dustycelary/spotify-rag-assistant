from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db import Base


class Lyrics(Base):
    __tablename__ = "lyrics"

    track_uri = Column(
        String(255), ForeignKey("tracks.uri", ondelete="CASCADE"), primary_key=True
    )
    raw_lyrics = Column(Text)
    cleaned_lyrics = Column(Text)
    song_description = Column(Text)
    genius_id = Column(Integer)
    updated_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    track = relationship("Track", back_populates="lyrics")
