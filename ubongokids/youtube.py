import youtube_dl
from collections import defaultdict

class CachingClient:
    def __init__(self, client, cache):
        self.client = client
        self.cache = cache

    def get_video_data(self, id):
        return self._get(self._gen_video_cache_key, id, self.client.get_video_data, self._cache_video)

    def get_playlist_data(self, id):
        return self._get(self._gen_playlist_cache_key, id, self.client.get_playlist_data, self._cache_playlist_parts)

    def get_channel_data(self, id):
        return self._get(self._gen_channel_cache_key, id, self.client.get_channel_data, self._cache_playlist_parts)

    def _get(self, cache_key_gen_func, id, get_func, further_caching_func):
        key = cache_key_gen_func(id)
        found, data = self.cache.get(key)
        if not found:
            data = get_func(id)
            self.cache.add(key, data)
            if further_caching_func:
                further_caching_func(data)
        return data

    def _cache_playlist_parts(self, enriched_playlist):
        playlist = enriched_playlist.get('_raw', {})
        assert playlist.get('_type', None) == 'playlist'
        for entry in playlist.get('entries'):
            self._cache_video(entry)

    def _cache_video(self, video):
        self.cache.add(self._gen_video_cache_key(video['id']), video)
        return video

    def _gen_playlist_cache_key(self, x):
        return f'playlist:{x}'

    def _gen_channel_cache_key(self, x):
        return f'channel:{x}'

    def _gen_video_cache_key(self, x):
        return f'video:{x}'

    def stats(self):
        return self.cache.stats()

class Client:
    def __init__(self, client):
        self.client = client

    def _get(self, url):
        return self.client.extract_info(url, download=False)

    def get_video_data(self, id):
        video = self._get(f'https://www.youtube.com/watch?v={id}')
        result = dict(url=video['webpage_url'])
        result.update(video)
        return result

    def get_playlist_data(self, id):
        playlist = self._get(f'https://www.youtube.com/playlist?list={id}')
        assert playlist.get('_type', None) == 'playlist'
        return dict(id=playlist['id'],
                    url=playlist['webpage_url'],
                    name=playlist['title'],
                    videos=[entry['id'] for entry in playlist.get('entries')],
                    _raw=playlist
        )

    def get_channel_data(self, id):
        channel = self._get(f'https://www.youtube.com/channel/{id}')
        assert channel.get('_type', None) == 'playlist'
        entries = channel.get('entries')
        name = channel['title']
        videos = [entry['id'] for entry in entries]
        return dict(id=channel['id'],
                    url=channel['webpage_url'],
                    name=name,
                    videos=videos,
                    playlists=[playlist_id for playlist_id in self._groupby(lambda x: x['playlist_id'], entries).keys()],
                    _raw=channel
        )

    def _groupby(self, key, seq):
        d = defaultdict(int)
        for item in seq:
            d[key(item)] += 1
        return d
