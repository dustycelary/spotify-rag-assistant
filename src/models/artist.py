from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db import Base
from src.models.track import track_artists


class Artist(Base):
    __tablename__ = "artists"

    uri = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    genres = Column(ARRAY(String(255)))
    popularity = Column(Integer)
    updated_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tracks = relationship("Track", secondary=track_artists, back_populates="artists")
