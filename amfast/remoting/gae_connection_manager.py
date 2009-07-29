import time
import pickle

from google.appengine.ext import db

from connection import Connection, ConnectionError
from connection_manager import ConnectionManager, NotConnectedError, SessionAttrError

class GaeConnection(Connection):
    """A connection stored in Google Datastore."""

    def __init__(self, *args, **kwargs):
        Connection.__init__(self, *args, **kwargs)
        self.key = None

class GaeModel(object):
    # Prefix id with this string to make a key_name
    KEY = 'K' 

    @classmethod
    def getKeyNameFromId(cls, id):
        return cls.KEY + id

    @classmethod
    def getIdFromKeyName(cls, key_name):
        return key_name.replace(cls.KEY, '', 1)

class GaeConnectionModel(db.Model, GaeModel):
    """Connection data that is stored in a Google Datastore."""

    # Stored attributes.
    channel_name = db.StringProperty(required=True)
    timeout = db.IntegerProperty(required=True)
    connected = db.BooleanProperty(required=True)
    last_active = db.FloatProperty(required=True)
    last_polled = db.FloatProperty(required=True)
    authenticated = db.BooleanProperty(required=True)
    flex_user = db.StringProperty(required=False)
    p_session = db.BlobProperty(required=False)

class GaeChannelModel(db.Model, GaeModel):

    name = db.StringProperty(required=True)
    count = db.IntegerProperty(required=True)

class GaeConnectionManager(ConnectionManager):
    """Manages connections stored by Google DataStore."""

    def __init__(self, connection_class=GaeConnection, connection_params=None):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

    def reset(self):
        query = GaeConnectionModel.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeChannelModel.all(keys_only=True)
        for result in query:
            db.delete(result)

    def _incrementChannelCount(self, channel_name):
        key = GaeChannelModel.getKeyNameFromId(channel_name)
        channel = GaeChannelModel.get_by_key_name(key)
        if channel is None:
            channel = GaeChannelModel(key_name=key,
                name=channel_name, count=1)
        else:
            channel.count += 1

        channel.put()

    def _decrementChannelCount(self, channel_name):
        key = GaeChannelModel.getKeyNameFromId(channel_name)
        channel = GaeChannelModel.get_by_key_name(key)
        if channel is not None:
            channel.count -= 1
            channel.put()

    def getConnectionCount(self, channel_name):
        key = GaeChannelModel.getKeyNameFromId(channel_name)
        channel = GaeChannelModel.get_by_key_name(key)
        if channel is None:
            return 0
        else:
            return channel.count
 
    def loadConnection(self, connection_id):
        stored_connection = GaeConnectionModel.get_by_key_name(\
            GaeConnectionModel.getKeyNameFromId(connection_id))
        
        if stored_connection is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        connection = self.connection_class(self, stored_connection.channel_name,
            connection_id, timeout=stored_connection.timeout)
        connection.key = stored_connection.key()
        return connection

    def initConnection(self, connection, channel):
        params = {
            'key_name': GaeConnectionModel.getKeyNameFromId(connection.id),
            'channel_name': connection.channel_name,
            'timeout': connection.timeout,
            'connected': True,
            'last_active': time.time() * 1000,
            'last_polled': 0.0,
            'authenticated': False
        }

        stored_connection = GaeConnectionModel(**params)
        stored_connection.put()

        db.run_in_transaction(self._incrementChannelCount,
            connection.channel_name)

        connection.key = stored_connection.key()

    def iterConnectionIds(self):
        query = GaeConnectionModel.all(keys_only=True)
        for key in query:
            yield GaeConnectionModel.getIdFromKeyName(key.name())

    # --- proxies for connection properties --- #

    def getConnected(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        if stored_connection is None:
            return False
        else:
            return stored_connection.connected

    def getLastActive(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        return stored_connection.last_active

    def getLastPolled(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        return stored_connection.last_polled

    def getAuthenticated(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        return stored_connection.authenticated

    def getFlexUser(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        return stored_connection.flex_user

    def getNotifyFunc(self, connection):
        return None

    # --- proxies for connection methods --- #

    def _deleteConnection(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        stored_connection.delete()

    def deleteConnection(self, connection):
        db.run_in_transaction(self._deleteConnection, connection)
        db.run_in_transaction(self._decrementChannelCount, connection.channel_name)
        ConnectionManager.deleteConnection(self, connection)

    def _connectConnection(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        if stored_connection is not None:
            stored_connection.connected = True
            stored_connection.put()

    def connectConnection(self, connection):
        db.run_in_transaction(self._connectConnection, connection)

    def _disconnectConnection(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        if stored_connection is not None:
            stored_connection.connected = False
            stored_connection.put()

    def disconnectConnection(self, connection):
        db.run_in_transaction(self._disconnectConnection, connection)

    def _touchConnection(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        stored_connection.last_active = time.time() * 1000
        stored_connection.put()

    def touchConnection(self, connection):
        db.run_in_transaction(self._touchConnection, connection)

    def _touchPolled(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        stored_connection.last_polled = time.time() * 1000
        stored_connection.put()

    def touchPolled(self, connection):
        db.run_in_transaction(self._touchPolled, connection)

    def _authenticateConnection(self, connection, user):
        stored_connection = GaeConnectionModel.get(connection.key)
        stored_connection.authenticated = True
        stored_connection.flex_user = user
        stored_connection.put()

    def authenticateConnection(self, connection, user):
        db.run_in_transaction(self._authenticateConnection, connection, user)

    def _unAuthenticateConnection(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)
        stored_connection.authenticated = False
        stored_connection.flex_user = None
        stored_connection.put()

    def unAuthenticateConnection(self, connection):
        db.run_in_transaction(self._unAuthenticateConnection, connection)

    def initSession(self, connection):
        stored_connection = GaeConnectionModel.get(connection.key)

        if not hasattr(stored_connection, 'p_session') or \
            stored_connection.p_session is None:
            stored_connection._session = {}
        else:
            stored_connection._session = pickle.loads(stored_connection.p_session)

        return stored_connection

    def saveSession(self, stored_connection):
        if hasattr(stored_connection, '_session'):
            stored_connection.p_session = pickle.dumps(stored_connection._session)
            stored_connection.put()

    def getConnectionSessionAttr(self, connection, name):
        stored_connection = self.initSession(connection)
        try:
            return stored_connection._session[name]
        except KeyError:
            raise SessionAttrError("Attribute '%s' not found." % name)

    def _setConnectionSessionAttr(self, connection, name, val):
        stored_connection = self.initSession(connection)
        stored_connection._session[name] = val
        self.saveSession(stored_connection)

    def setConnectionSessionAttr(self, connection, name, val):
        db.run_in_transaction(self._setConnectionSessionAttr, connection, name, val)

    def _delConnectionSessionAttr(self, connection, name):
        stored_connection = self.initSession(connection)
        try:
            del stored_connection._session[name]
            self.saveSession(stored_connection)
        except KeyError:
            pass

    def delConnectionSessionAttr(self, connection, name):
        db.run_in_transaction(self._delConnectionSessionAttr, connection, name)
