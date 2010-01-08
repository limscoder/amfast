import time
import uuid

try:
    # Load Google's special API if we're running
    # under GAE, and set flag so we know.
    import google.appengine.api.memcache as memcache
    google = True
except ImportError:
    import memcache
    google = False

class MemcacheMutex(object):
    """Blocks access to a specific key. Locking will fail if lock element is pushed out of cache."""

    def __init__(self, mc):
        self.mc = mc
        self.id = str(uuid.uuid4())
        self.acquired_locks = {}

    def acquire(self, key):
        lock_holder = self.mc.get(key)
        while lock_holder != self.id:
            if lock_holder is None:
                self.mc.set(key, self.id)
            else:
                time.sleep(0.1)
            lock_holder = self.mc.get(key)

        self.acquired_locks[key] = True

    def release(self, key, force=False):
        if key in self.acquired_locks or force is True:
            self.mc.delete(key)
            del self.acquired_locks[key]

    def releaseAll(self):
        self.mc.delete_multi(self.acquired_locks.keys())
        self.acquired_locks = {}

class MemcacheManager(object):
    KEY_SEPARATOR = '_'

    LOCK = '_lock'

    @classmethod
    def createMcClient(cls, mc_servers=("127.0.0.1:11211",), mc_debug=0):
        if google is True:
            return memcache.Client()
        else:
            return memcache.Client(mc_servers, mc_debug)

    @classmethod
    def getKeyName(cls, connection_id, attr):
        return str(cls.KEY_SEPARATOR.join((connection_id, str(attr))))

    @classmethod
    def getLockName(cls, attr):
        return str(cls.KEY_SEPARATOR.join((cls.LOCK, attr)))
