from dataclasses import dataclass
from datetime import datetime


@dataclass
class Track:
    uri: str
    name: str
    artist: str
    release_date: datetime
    lyrics: str | None = None
