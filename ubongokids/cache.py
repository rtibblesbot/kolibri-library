import logging
from os import makedirs
from os.path import join
from json import dump
import shelve


logger = logging.getLogger(__name__)


class Db:
    def __init__(self, basedir, suffix):
        self.basedir = basedir
        self.db_path = join(basedir, "cache{}".format(suffix))
        self.hits = 0
        self.misses = 0
        makedirs(self.basedir, exist_ok=True)
        self.db = shelve.open(self.db_path)

    def add(self, key, data):
        self.db[key] = data

    def remove(self, key):
        del self.db[key]

    def get(self, key):
        if key in self.db:
            logger.debug("Cache hit for {}".format(key))
            self.hits += 1
            return (True, self.db[key])
        else:
            logger.debug("Cache miss for {}".format(key))
            self.misses += 1
            return (False, None)

    def stats(self):
        return dict(hits=self.hits, misses=self.misses)

    def __del__(self):
        with open(self.db_path + ".cache_stats.json", "w") as f:
            dump(self.stats(), f)
        self.db.close()
