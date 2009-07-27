import time

import memcache_manager
from connection import Connection, ConnectionError
from connection_manager import ConnectionManager, NotConnectedError

class MemcacheConnectionManager(ConnectionManager, memcache_manager.MemcacheManager):
    """Manages connections stored by Memcache."""

    CONNECTIONS_ATTR = '_connection_ids'

    ATTRIBUTES = ('connection_info', 'connected', 'last_active',
        'last_polled', 'authenticated', 'flex_user', 'session', 'notify_func_id')

    def __init__(self, connection_class=Connection, connection_params=None,
        mc_servers=['127.0.0.1:11211'], mc_debug=0):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

        self.mc = self.createMcClient(mc_servers, mc_debug)
        if self.mc.get(self.CONNECTIONS_ATTR) is None:
            self.mc.set(self.CONNECTIONS_ATTR, [])
        self._lock = memcache_manager.MemcacheMutex(self.mc)

    def checkMultiSetResults(self, results):
        if len(results) > 0:
           msg = 'The following parameters were not set: ' + ', '.join(results)
           raise ConnectionError(msg)

    def loadConnection(self, connection_id):
        connection_info = self.mc.get(self.getKeyName(connection_id, 'connection_info'))
        
        if connection_info is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        return self.connection_class(self, connection_info['channel_name'],
            connection_id, connection_info['timeout'])

    def initConnection(self, connection):
        params = {
            'connected': True,
            'last_active': time.time() * 1000,
            'last_polled': 0.0,
            'authenticated': False,
            'session': {}
        }

        connection_info = {
            'channel_name': connection.channel_name,
            'timeout': connection.timeout
        }

        cache_params = {}
        for key, val in params.iteritems():
            cache_params[self.getKeyName(connection.id, key)] = val
        cache_params[self.getKeyName(connection.id, 'connection_info')] = connection_info

        self.checkMultiSetResults(self.mc.set_multi(cache_params))

        lock_name = self.getLockName(self.CONNECTIONS_ATTR)
        self._lock.acquire(lock_name)
        try:
            connection_ids = self.mc.get(self.CONNECTIONS_ATTR)
            connection_ids.append(connection.id)
            self.mc.set(self.CONNECTIONS_ATTR, connection_ids)
        finally:
            self._lock.release(lock_name)

    def iterConnectionIds(self):
        connection_ids = self.mc.get(self.CONNECTIONS_ATTR)
        return connection_ids.__iter__() 

    # --- proxies for connection properties --- #

    def getConnected(self, connection):
        return self.mc.get(self.getKeyName(connection.id, 'connected'))

    def getLastActive(self, connection):
        return self.mc.get(self.getKeyName(connection.id, 'last_active'))

    def getLastPolled(self, connection):
        return self.mc.get(self.getKeyName(connection.id, 'last_polled'))

    def getAuthenticated(self, connection):
        return self.mc.get(self.getKeyName(connection.id, 'authenticated'))

    def getFlexUser(self, connection):
        return self.mc.get(self.getKeyName(connection.id, 'flex_user'))

    def getNotifyFunc(self, connection):
        notify_func_id = self.mc.get(self.getKeyName(connection.id, 'notify_func_id'))

        if notify_func_id is None:
            return None
        else:
            return connection._getNotifyFuncById(connection._notify_func_id)

    # --- proxies for connection methods --- #

    def deleteConnection(self, connection):
        lock_name = self.getLockName(self.CONNECTIONS_ATTR)
        self._lock.acquire(lock_name)
        try:
            connection_ids = self.mc.get(self.CONNECTIONS_ATTR)
            for i, connection_id in enumerate(connection_ids):
                if connection_id == connection.id:
                    connection_ids.pop(i)
                    break
            self.mc.set(self.CONNECTIONS_ATTR, connection_ids)
        finally:
            self._lock.release(lock_name)

        keys = [self.getKeyName(connection.id, attr) for attr in self.ATTRIBUTES]
        self.mc.delete_multi(keys)

    def touchConnection(self, connection):
        self.mc.set(self.getKeyName(connection.id, 'last_active'), time.time() * 1000)

    def touchPolled(self, connection):
        self.mc.set(self.getKeyName(connection.id, 'last_polled'), time.time() * 1000)

    def authenticateConnection(self, connection, user):
        params = {
            self.getKeyName(connection.id, 'authenticated'): True,
            self.getKeyName(connection.id, 'flex_user'): user
        }

        self.checkMultiSetResults(self.mc.multi_set(params))

    def unAuthenticateConnection(self, connection):
        self.mc.set(self.getKeyName(connection.id, 'authenticated'), False)
        self.mc.delete(self.getKeyName(connection.id, 'flex_user'))

    def setNotifyFunc(self, connection, func):
        self.mc.set(self.getKeyName(connection.id, 'notify_func_id'),
            connection._setNotifyFunc(func))

    def unSetNotifyFunc(self, connection):
        self.mc.delete(self.getKeyName(connection.id, 'notify_func_id'))

    def getConnectionSessionAttr(self, connection, name):
        session = self.mc.get(self.getKeyName(connection.id, 'session'))
        return session[name]

    def setConnectionSessionAttr(self, connection, name, val):
        key = self.getKeyName(connection.id, 'session')

        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            session = self.mc.get(key)
            session[name] = val
            self.mc.set(key, session)
        finally:
            self._lock.release(lock_name)

    def delConnectionSessionAttr(self, connection, name):
        key = self.getKeyName(connection.id, 'session')

        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            session = self.mc.get(key)
            del session[name]
            self.mc.set(key, session)
        finally:
            self._lock.release(lock_name)
