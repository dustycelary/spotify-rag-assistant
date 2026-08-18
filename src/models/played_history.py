from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db import Base


class PlayedHistory(Base):
    __tablename__ = "played_history"
    __table_args__ = (
        UniqueConstraint("track_uri", "played_at", name="unique_history_play"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_uri = Column(String(255), ForeignKey("tracks.uri", ondelete="CASCADE"))
    played_at = Column(DateTime(timezone=True), nullable=False)
    context_type = Column(String(50))
    context_uri = Column(String(255))
    inserted_at = Column(DateTime, server_default=func.current_timestamp())
    played_time = Column(Integer, nullable=False, default=0)

    # Relationships
    track = relationship("Track", back_populates="played_history")
