import logging


logger = logging.getLogger(__name__)

from pressurecooker.youtube import YouTubeResource


class CachingClient:
    def __init__(self, client, cache):
        self.client = client
        self.cache = cache

    def get_video_data(self, id):
        return self._get(
            self._gen_video_cache_key, id, self.client.get_video_data, self._cache_video
        )

    def get_playlist_data(self, id):
        return self._get(
            self._gen_playlist_cache_key,
            id,
            self.client.get_playlist_data,
            None,
        )

    def get_channel_data(self, id):
        return self._get(
            self._gen_channel_cache_key,
            id,
            self.client.get_channel_data,
            None,
        )

    def _get(self, cache_key_gen_func, id, get_func, further_caching_func):
        key = cache_key_gen_func(id)
        found, data = self.cache.get(key)
        if not found:
            data = get_func(id)
            self.cache.add(key, data)
            if further_caching_func:
                further_caching_func(data)
        return data

    def _cache_video(self, video):
        self.cache.add(self._gen_video_cache_key(video["id"]), video)
        return video

    def _gen_playlist_cache_key(self, x):
        return "playlist:{}".format(x)

    def _gen_channel_cache_key(self, x):
        return "channel:{}".format(x)

    def _gen_video_cache_key(self, x):
        return "video:{}".format(x)

    def stats(self):
        return self.cache.stats()


class Client:
    def __init__(self, client):
        self.client = client

    def _get(self, url):
        try:
            return self.client.extract_info(url, download=False)
        except Exception:
            # Exception info lacks URL
            logger.error("Error fetching url: {}".format(url))
            raise

    def get_video_data(self, id):
        video_url = "https://www.youtube.com/watch?v={}".format(id)
        ytres = YouTubeResource(video_url)
        video_info = ytres.get_resource_info()
        result = dict(url=video_url)
        result.update(video_info)
        return result

    def get_playlist_data(self, id):
        playlist = self._get("https://www.youtube.com/playlist?list={}".format(id))
        if playlist.get("_type", None) != "playlist":
            logger.error("Got this data: {}".format(playlist))
            raise AssertionError("Not a playlist")
        return dict(
            id=playlist["id"],
            url=playlist["webpage_url"],
            name=playlist["title"],
            videos=[entry["id"] for entry in playlist.get("entries")],
        )

    def get_channel_data(self, id):
        # Firstly, get all the playlists
        channel = self._get("https://www.youtube.com/channel/{}/playlists".format(id))
        if channel.get("_type", None) != "playlist":
            logger.error("Got this data: {}".format(channel))
            raise AssertionError("Not a url reference")
        
        def get_playlist_id(url):
            """
            Example:
            https://www.youtube.com/playlist?list=PLjSFjqcCS3M-OdPo7sZZSwpK5d1KL4kAR
            """
            __, playlist_id = url.split("=")
            return playlist_id
        
        entries = channel.get("entries")
        name = channel["title"]
        return dict(
            id=channel["id"],
            url=channel["webpage_url"],
            name=name,
            playlists=[get_playlist_id(entry['url']) for entry in entries],
        )

