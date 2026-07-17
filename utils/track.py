from dataclasses import dataclass
from datetime import datetime


@dataclass
class Track:
    id: str
    name: str
    artist: str
    lyrics: str
    release_date: datetime
