import certifi
from croniter import croniter
from datetime import datetime, timezone
from pymongo import TEXT, UpdateOne, MongoClient


class MongoDB:
    def __init__(self, domain: str, username: str, password: str):
        self.domain = domain
        self.username = username
        self.password = password
        self.tlsca_ = certifi.where()
        self.client = MongoClient(
            f"mongodb+srv://{username}:{password}@{domain}/?retryWrites=true&w=majority",
            tlsCAFile=self.tlsca_,
        )
        self.db = self.client["main"]
        self.metadata = self.client["metadata"]

        self.config_col = self.db["config"]
        self.history_col = self.db["history"]
        self.other_col = self.db["other"]
        self.watchlist_col = self.db["watchlist"]

        self.movies_col = self.metadata["movies"]
        self.movies_cache_col = self.metadata["movies_cache"]
        self.series_col = self.metadata["series"]
        self.series_cache_col = self.metadata["series_cache"]

        self.config = {
            "app": {},
            "auth0": {},
            "categories": [],
            "gdrive": {},
            "tmdb": {},
            "build": {},
            "rclone": [],
        }
        self.get_config()
        self.is_config_init = False
        self.get_is_config_init()
        self.is_metadata_init = False
        self.get_is_metadata_init()
        self.is_series_cache_init = False
        self.get_is_metadata_init()
        self.is_movies_cache_init = False
        self.get_is_movies_cache_init()
        self.is_series_cache_init = False
        self.get_is_series_cache_init()

    def get_config(self) -> dict:
        config = {
            "_id": None,
            "app": {},
            "auth0": {},
            "categories": [],
            "gdrive": {},
            "tmdb": {},
            "build": {},
            "rclone": [],
        }
        for document in self.config_col.find():
            config = config | document
        del config["_id"]
        self.config = config
        return config

    def get_is_config_init(self) -> bool:
        result = self.other_col.find_one({"is_config_init": {"$exists": True}}) or {
            "is_config_init": False
        }
        self.is_config_init = result["is_config_init"]
        return result["is_config_init"]

    def get_is_metadata_init(self) -> bool:
        result = self.other_col.find_one({"is_metadata_init": {"$exists": True}}) or {
            "is_metadata_init": False
        }
        self.is_metadata_init = result["is_metadata_init"]
        return result["is_metadata_init"]

    def get_is_movies_cache_init(self) -> bool:
        result = self.other_col.find_one(
            {"is_movies_cache_init": {"$exists": True}}
        ) or {"is_movies_cache_init": False}
        self.is_movies_cache_init = result["is_movies_cache_init"]
        return result["is_movies_cache_init"]

    def get_is_series_cache_init(self) -> bool:
        result = self.other_col.find_one(
            {"is_series_cache_init": {"$exists": True}}
        ) or {"is_series_cache_init": False}
        self.is_series_cache_init = result["is_series_cache_init"]
        return result["is_series_cache_init"]

    def get_is_build_time(self) -> bool:
        build_config = self.config_col.find_one({"build": {"$exists": True}}) or {
            "build": {"cron": "*/120 * * * *"}
        }
        last_build_time = self.other_col.find_one(
            {"last_build_time": {"$exists": True}}
        ) or {"last_build_time": datetime.fromtimestamp(1, tz=timezone.utc)}
        cron = croniter(
            build_config["build"].get("cron", "*/120 * * * *"), last_build_time
        )
        if datetime.now(timezone.utc) > cron.get_next(datetime):
            return True
        else:
            return False

    def get_rclone_conf(self) -> dict:
        result = self.config_col.find_one({"rclone": {"$exists": True}}) or {
            "rclone": []
        }
        rclone_conf = "\n\n".join(result["rclone"])
        self.config["rclone_conf"] = rclone_conf
        return rclone_conf

    def get_categories(self) -> list:
        result = self.config_col.find_one({"categories": {"$exists": True}}) or {
            "categories": []
        }
        self.config["categories"] = result["categories"]
        return result["categories"]

    def get_tmbd_api_key(self) -> str:
        result = self.config_col.find_one({"tmdb": {"$exists": True}}) or {
            "tmdb": {"api_key": ""}
        }
        tmdb_api_key = result["tmdb"].get("api_key", "")
        self.tmdb_api_key = tmdb_api_key
        return tmdb_api_key

    def set_config(self, data: dict) -> int:
        from app.core import build_config

        bulk_action: list = []
        config_app: dict = data.get("app", {})
        config_auth0: dict = data.get("auth0", {})
        config_categories: list = data.get("categories", [])
        config_gdrive: dict = data.get("gdrive", {})
        config_tmdb: dict = data.get("tmdb", {})
        config_build: dict = data.get("build", {})

        if config_app != self.config["app"]:
            bulk_action.append(self.set_app(config_app))
        if config_auth0 != self.config["auth0"]:
            bulk_action.append(self.set_auth0(config_auth0))
        if config_gdrive != self.config["gdrive"]:
            bulk_action.append(self.set_gdrive(config_gdrive))
        if config_tmdb != self.config["tmdb"]:
            bulk_action.append(self.set_tmdb(config_tmdb))
        if config_build != self.config["build"]:
            bulk_action.append(self.set_build(config_build))
        if config_categories != self.config["categories"]:
            bulk_action.append(self.set_categories(config_categories))
            config_rclone = build_config(self.config)
            bulk_action.append(self.set_rclone(config_rclone))
            self.set_is_metadata_init(False)

        if len(bulk_action) == 0:
            return 0
        self.config_col.bulk_write(bulk_action)
        self.set_is_config_init(True)

        if self.is_metadata_init is False:
            from main import rclone_setup

            rclone_setup(self.config["categories"])
            return 2
        return 1

    def set_app(self, data: dict):
        update_data: dict = {
            "name": data.get("name", "Dester"),
            "title": data.get("title", "Dester"),
            "description": data.get("description", "Dester"),
            "domain": data.get("domain", ""),
        }
        update_action: UpdateOne = UpdateOne(
            {"app": {"$exists": True}}, {"$set": {"app": update_data}}, upsert=True
        )
        self.config["app"] = update_data
        return update_action

    def set_auth0(self, data: dict):
        update_data: dict = {
            "client_id": data.get("client_id", ""),
            "client_secret": data.get("client_secret", ""),
            "domain": data.get("domain", ""),
        }
        update_action: UpdateOne = UpdateOne(
            {"auth0": {"$exists": True}}, {"$set": {"auth0": update_data}}, upsert=True
        )
        self.config["auth0"] = update_data
        return update_action

    def set_categories(self, data: list):
        update_data: list = []
        for item in data:
            update_data.append(
                {
                    "drive_id": item.get("drive_id"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("type", "movies"),
                    "provider": item.get("provider"),
                    "language": item.get("language", "en"),
                    "adult": item.get("adult", False),
                    "anime": item.get("anime", False),
                }
            )
        update_action: UpdateOne = UpdateOne(
            {"categories": {"$exists": True}},
            {"$set": {"categories": update_data}},
            upsert=True,
        )
        self.config["categories"] = update_data
        return update_action

    def set_gdrive(self, data: dict):
        update_data: dict = {
            "client_id": data.get("client_id", ""),
            "client_secret": data.get("client_secret", ""),
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
        }
        update_action: UpdateOne = UpdateOne(
            {"gdrive": {"$exists": True}},
            {"$set": {"gdrive": update_data}},
            upsert=True,
        )
        self.config["gdrive"] = update_data
        return update_action

    def set_tmdb(self, data: dict):
        update_data: dict = {"api_key": data.get("api_key", "")}
        update_action: UpdateOne = UpdateOne(
            {"tmdb": {"$exists": True}}, {"$set": {"tmdb": update_data}}, upsert=True
        )
        self.config["tmdb"] = update_data
        return update_action

    def set_build(self, data: dict):
        update_data: dict = {"cron": data.get("cron", "*/120 * * * *")}
        update_action: UpdateOne = UpdateOne(
            {"build": {"$exists": True}}, {"$set": {"build": update_data}}, upsert=True
        )
        self.config["build"] = update_data
        return update_action

    def set_rclone(self, data: list):
        update_data: list = data
        update_action: UpdateOne = UpdateOne(
            {"rclone": {"$exists": True}},
            {"$set": {"rclone": update_data}},
            upsert=True,
        )
        self.config["rclone"] = update_data
        return update_action

    def set_is_config_init(self, is_config_init: bool):
        if is_config_init != self.is_config_init:
            self.other_col.update_one(
                {"is_config_init": {"$exists": True}},
                {"$set": {"is_config_init": is_config_init}},
                upsert=True,
            )
            self.is_config_init = is_config_init
        return

    def set_is_metadata_init(self, is_metadata_init: bool):
        if is_metadata_init != self.is_metadata_init:
            self.other_col.update_one(
                {"is_metadata_init": {"$exists": True}},
                {"$set": {"is_metadata_init": is_metadata_init}},
                upsert=True,
            )
            self.is_metadata_init = is_metadata_init
        return

    def set_is_movies_cache_init(self, is_movies_cache_init: bool):
        if is_movies_cache_init != self.is_movies_cache_init:
            self.movies_cache_col.create_index(
                [("original_title", TEXT)], background=True, name="original_title"
            )
            self.other_col.update_one(
                {"is_movies_cache_init": {"$exists": True}},
                {"$set": {"is_movies_cache_init": is_movies_cache_init}},
                upsert=True,
            )
            self.is_metadata_init = is_movies_cache_init
        return

    def set_is_series_cache_init(self, is_series_cache_init: bool):
        if is_series_cache_init != self.is_series_cache_init:
            self.series_cache_col.create_index(
                [("original_title", TEXT)], background=True, name="original_title"
            )
            self.other_col.update_one(
                {"is_series_cache_init": {"$exists": True}},
                {"$set": {"is_series_cache_init": is_series_cache_init}},
                upsert=True,
            )
            self.is_series_cache_init = is_series_cache_init
        return
