from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db import Base


class Embedding(Base):
    __tablename__ = "embeddings"

    track_uri = Column(
        String(255), ForeignKey("tracks.uri", ondelete="CASCADE"), primary_key=True
    )
    embedding = Column(Vector(384))
    updated_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    track = relationship("Track", back_populates="embedding")


# Create the HNSW index for the embeddings table based on vector_cosine_ops
Index(
    "embeddings_hnsw_idx",
    Embedding.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
