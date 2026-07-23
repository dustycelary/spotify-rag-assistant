import inspect

from src.spotify_tools import SpotifyTools


class SpotifyAgent:
    """Responsible for query routing, determine user intention"""

    def __init__(self, db_conn, model_name: str = "llama3.2"):
        self.model_name = model_name
        self.tools = SpotifyTools(db_conn)

        self.available_tools = {
            name: method
            for name, method in inspect.getmembers(self.tools, inspect.ismethod)
            if getattr(method, "is_available", False)
        }

    def run():
        # asking model at start for tools, running functoins, passing them back to ai model

        pass
