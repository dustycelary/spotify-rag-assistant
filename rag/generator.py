import ollama


class Generator:
    def generate_response(self, user_question: str, retrieved_data: list[dict]) -> str:
        """"""
        context_blocks = []
        for doc in retrieved_data:
            context_blocks.append(
                f"Song: {doc['title']} by {doc['artist']}\n"
                f"Lyrics:\n{doc['cleaned_lyrics']}\n"
            )
        context = "\n---\n".join(context_blocks)

        # HACK: can i improve the prompt?
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
