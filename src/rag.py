import ollama
from sentence_transformers import SentenceTransformer


def embed_text(text: str, model: SentenceTransformer | None = None) -> list[float]:
    """Generates 384-dimensional vector for text argument"""
    if not model:
        model = SentenceTransformer("all-MiniLM-L6-v2")

    return model.encode(text).tolist()


def generate_user_response(user_question: str, context: list[dict]) -> str:
    """"""
    context_blocks = []
    for doc in context:
        context_blocks.append(
            f"Song: {doc['title']} by {doc['artist']}\n"
            f"Lyrics:\n{doc['cleaned_lyrics']}\n"
        )
    context = "\n---\n".join(context_blocks)

    prompt = f"""  
        As my spotify music assisstant, answer the users question 
        solely based on the supplied context. 

        Context: 
            {context}

        Question:
            {user_question}
    """

    # llama3 as its free and secure (local).
    response = ollama.generate(model="llama3.2", prompt=prompt)
    # Extract the response string from Ollama's result dictionary
    if isinstance(response, dict):
        return response.get("response", "")
    return getattr(response, "response", str(response))
