from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db import Base

# Association table for the many-to-many relationship between tracks and artists
track_artists = Table(
    "track_artists",
    Base.metadata,
    Column(
        "track_uri",
        String(255),
        ForeignKey("tracks.uri", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "artist_uri",
        String(255),
        ForeignKey("artists.uri", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Track(Base):
    __tablename__ = "tracks"

    uri = Column(String(255), primary_key=True)
    title = Column(String(255), nullable=False)
    album_name = Column(String(255))
    album_uri = Column(String(255))
    release_date = Column(Date)
    popularity = Column(Integer)
    duration_ms = Column(Integer)
    updated_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    artists = relationship("Artist", secondary=track_artists, back_populates="tracks")
    audio_features = relationship(
        "AudioFeatures",
        back_populates="track",
        uselist=False,
        cascade="all, delete-orphan",
    )
    lyrics = relationship(
        "Lyrics", back_populates="track", uselist=False, cascade="all, delete-orphan"
    )
    played_history = relationship(
        "PlayedHistory", back_populates="track", cascade="all, delete-orphan"
    )
    embedding = relationship(
        "Embedding", back_populates="track", uselist=False, cascade="all, delete-orphan"
    )
