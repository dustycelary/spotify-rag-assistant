from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db import Base


class AudioFeatures(Base):
    __tablename__ = "audio_features"

    track_uri = Column(
        String(255), ForeignKey("tracks.uri", ondelete="CASCADE"), primary_key=True
    )
    valence = Column(Float)
    energy = Column(Float)
    danceability = Column(Float)
    tempo = Column(Float)
    acousticness = Column(Float)
    instrumentalness = Column(Float)
    liveness = Column(Float)
    loudness = Column(Float)
    speechiness = Column(Float)
    updated_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    track = relationship("Track", back_populates="audio_features")
