from datetime import datetime
from app.models import Episode
from dateutil.parser import isoparse


class Season:
    __slots__ = [
        "id",
        "file_name",
        "path",
        "parent",
        "modified_time",
        "tmdb_id",
        "name",
        "overview",
        "air_date",
        "episode_count",
        "season_number",
        "poster_path",
        "episodes",
    ]

    def __dict__(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "path": self.path,
            "parent": self.parent,
            "modified_time": self.modified_time,
            "tmdb_id": self.tmdb_id,
            "name": self.name,
            "overview": self.overview,
            "air_date": self.air_date,
            "episode_count": self.episode_count,
            "season_number": self.season_number,
            "poster_path": self.poster_path,
            "episodes": self.episodes,
        }

    def __init__(self, file_metadata, media_metadata):
        # File Info
        self.id: str = file_metadata["id"]
        self.file_name: str = file_metadata["name"]
        self.path: str = file_metadata["path"]
        self.parent: dict = file_metadata["parent"]
        self.modified_time: datetime = isoparse(file_metadata["modified_time"])

        # Media Info
        self.tmdb_id: int = media_metadata["_id"]
        self.name: str = media_metadata["name"]
        self.overview: str = media_metadata["overview"]
        air_date: str = media_metadata["air_date"]
        self.air_date: datetime = datetime.strptime(air_date, "%Y-%m-%d")
        self.episode_count: int = len(media_metadata["episodes"])
        self.season_number: int = media_metadata["season_number"]

        # Media Resources
        self.poster_path: str = media_metadata["poster_path"]

        # Episodes
        index: int = len(file_metadata["episodes"])
        self.episodes: dict = {}
        for episode in file_metadata["episodes"]:
            episode_meta: Episode = Episode(episode, media_metadata, index)
            self.episodes[str(episode_meta.episode_number)] = episode_meta.__dict__()
            index -= 1
