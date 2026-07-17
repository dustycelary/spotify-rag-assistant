from dataclasses import dataclass
from datetime import datetime


@dataclass
class Track:
    uri: str
    name: str
    artist: str
    lyrics: str | None = None
    release_date: datetime
