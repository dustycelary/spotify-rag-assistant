import psycopg2
from rag import embedder
from rag import generator
from rag import retriever


class RagController:
    # TODO: what to put as doc string?

    def __init__(self, conn: psycopg2.extensions.connection):
        self.conn = conn

    def query(self, user_question: str) -> str:
        query_embedder = embedder.Embedder()
        query_vector = query_embedder.embed_text(user_question)

        track_retriever = retriever.Retriever(self.conn)
        similar_tracks = track_retriever.search_similar_lyrics(query_vector)

        response_generator = generator.Generator()
        return response_generator.generate_response(user_question, similar_tracks)
