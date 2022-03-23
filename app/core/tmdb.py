import gzip
import httpx
import os.path
import ujson as json
from app.models import DataType
from difflib import SequenceMatcher
from typing import Any, Dict, Optional
from datetime import datetime, timedelta



class TMDB:
    def __init__(self, api_key: str):
        if not os.path.exists('./cache/movie_ids.json'):
            self.export_data(DataType.movie)
        if not os.path.exists('./cache/tv_series_ids.json'):
            self.export_data(DataType.series)
        self.movie_export_data = json.load(open('./cache/movie_ids.json', 'r', encoding='utf-8'))
        self.series_export_data = json.load(open('./cache/tv_series_ids.json', 'r', encoding='utf-8'))
        self.client = httpx.Client(params={'api_key': api_key})
        self.config = self.get_server_config()
        self.image_base_url = self.config['images']['secure_base_url']

    def get_server_config(self) -> Dict[str, Any]:
        """Get the server config from the API

        Returns:
            dict: The server config
        """
        url = "https://api.themoviedb.org/3/configuration"
        response = self.client.get(url)
        return response.json()
    
    @staticmethod
    def export_data(data_type: DataType):
        print(f"Exporting {data_type} data")
        date_str = (datetime.now() - timedelta(days=1)).strftime('%m_%d_%Y')
        type_name = 'tv_series' if data_type == DataType.series else 'movie'
        export_url = f"http://files.tmdb.org/p/exports/{type_name}_ids_{date_str}.json.gz" 
        movie_json = gzip.decompress(
                        httpx.get(export_url).content
                    ).decode('utf-8')
        data = [json.loads(line) for line in movie_json.split('\n') if line]
        data = sorted(data, key=lambda x: x['id'])
        json.dump(data, open(f'./cache/{type_name}_ids.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False, sort_keys=True)

    def get_episode_details(self, tmdb_id: int, episode_number: int, season_number: int = 1) -> Dict[str, Any]:
        """Get the details of a specific episode from the API
        
        Args:
            tmdb_id (int): The TMDB ID of the episode
            episode_number (int): The episode number
            season_number (int, optional): The season number

        Returns:
            dict: The episode details
        """
        url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}"
        response = self.client.get(url)
        return response.json() if response.status_code == 200 else {}
    
    def find_media_id(self, title: str, data_type: DataType, year: Optional[int] = None, adult: bool = False) -> Optional[int]:
        """The legacy way to get TMDB ID for a title
        it consumes a bit more memory and it's slower
        but the result is more accurate

        Args:
            title (str): The title of the movie / series
            data_type (DataType): The type of the title

        Returns:
            None
        """
        from app.utils.data import clean_file_name
        title = title.lower().strip()
        original_title = title
        title = clean_file_name(title)
        if not title:
            print(f"The parsed title returned an empty string. Skipping...")
            print(f"Original Title: {original_title}")
            return None
        print("Trying search using API for {}".format(title))
        type_name = 'tv' if data_type == DataType.series else 'movie'
        resp = self.client.get(f"https://api.themoviedb.org/3/search/{type_name}", params={'query': title, 'primary_release_year': year,
                                                                                           'include_adult': adult, 'page': 1, 'language': 'en-US'})
        if resp.status_code == 200:
            if data := resp.json()['results']:
                return data[0]['id']
        
        print("API Search Failed!")
        key_name = 'original_name' if data_type == DataType.series else 'original_title'
        data = self.movie_export_data if data_type == DataType.movie else self.series_export_data
        print("Trying search using key-value search for {}".format(title))
        for each in data:
            if title == each.get(key_name).lower().strip():
                return each["id"]
        print("Basic key-value search failed.")
        max_ratio, match = 0, None
        matcher = SequenceMatcher(b=title)
        print("Trying search using difflib advanced search for {}".format(title))
        for each in data:
            matcher.set_seq1(each[key_name].lower().strip())
            ratio = matcher.ratio()
            if ratio > 0.99:
                return each
            if ratio > max_ratio and ratio >= 0.85:
                max_ratio = ratio
                match = each
        if match:
            return match["id"]
        print("Advanced difflib search failed.")
    
    def get_details(self, tmdb_id: int, data_type: DataType) -> Dict[str, Any]:
        """Get the details of a movie / series from the API

        Args:
            tmdb_id (int): The TMDB ID of the movie / series
            data_type (DataType): The type of the title

        Returns:
            dict: The details of the movie / series
        """
        type_name = 'tv' if data_type == DataType.series else 'movie'
        url = f"https://api.themoviedb.org/3/{type_name}/{tmdb_id}"
        response = self.client.get(url, params={'include_image_language': 'en',
                                                'append_to_response': 'credits,images,episode_groups,recommendations,similar,external_ids'})
        return response.json()