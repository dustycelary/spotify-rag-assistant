from sentence_transformers import SentenceTransformer


class Embedder:
    """Helper class to convert song lyrics into 384-dimensional vector stored in
    ../pipeline/schema/05_embeddings.sql"""

    def __init__(
        self, model_name: str = "all-MiniLM-L6-v2"
    ):  # NOTE: def because its lightweight and fast, appropriate for lots of devices.
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        """Generates 384-dimensional vector for text argument"""
        return self.model.encode(text).tolist()
