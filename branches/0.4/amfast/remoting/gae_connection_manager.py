import time
import pickle

from google.appengine.ext import db

from connection import Connection
from connection_manager import ConnectionManager, NotConnectedError

class GaeConnection(db.Model, Connection):
    """A connection that is persisted in a Google Datastore."""

    _id = db.StringProperty(required=True)
    _channel_name = db.StringProperty(required=True)
    _timeout = db.IntegerProperty(required=True)
    _connected = db.BooleanProperty(required=True)
    _last_active = db.FloatProperty(required=True)
    _last_polled = db.FloatProperty(required=True)
    _authenticated = db.BooleanProperty(required=True)
    _flex_user = db.StringProperty(required=False)
    _p_session = db.BlobProperty(required=False)

class GaeConnectionManager(ConnectionManager):
    """Manages connections stored by Google DataStore."""

    # Prefix id with this string to make a key_name
    KEY = 'K'

    def __init__(self, connection_class=GaeConnection, connection_params=None):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

    def getKeyName(self, id):
        return self.KEY + id

    def getIdFromKey(self, key_name):
        return key_name.replace(self.KEY, '', 1)

    def loadConnection(self, connection_id):
        connection = GaeConnection.get_by_key_name(self.getKeyName(connection_id))
        
        if connection is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        connection._manager = self
        return connection
        
    def createConnection(self, channel, connection_id=None):
        if connection_id is None:
            connection_id = self.generateId()

        defaults = {
            'key_name': self.getKeyName(connection_id),
            '_id': connection_id,
            '_channel_name': channel.name,
            '_timeout': 1800000,
            '_connected': True,
            '_last_active': time.time(),
            '_last_polled': 0.0,
            '_authenticated': False
        }

        defaults.update(self.connection_params)

        connection = self.connection_class(**defaults)
        connection._manager = self
        connection.put()
        return connection

    def deleteConnection(self, connection):
        connection.delete()
        ConnectionManager.deleteConnection(self, connection)

    def iterConnectionIds(self):
        query = GaeConnection.all(keys_only=True)
        for key in query:
            yield self.getIdFromKey(key.name())

    def touchConnection(self, connection):
        connection._last_active = time.time() * 1000
        connection.put()

    def touchPolled(self, connection):
        connection._last_polled = time.time() * 1000
        connection.put()

    def authenticateConnection(self, connection, user):
        connection._authenticated = True
        connection._flex_user = user
        connection.put()

    def unAuthenticateConnection(self, connection):
        connection._authenticated = False
        connection._flex_user = None
        connection.put()

    def initSession(self, connection):
        if not hasattr(connection, '_session'):
            if not hasattr(connection, '_p_session'):
                connection._session = {}
            else:
                connection._session = pickle.loads(connection._p_session)

    def saveSession(self, connection):
        if hasattr(connection, '_session'):
            connection._p_session = pickle.dumps(connection._session)

    def getConnectionSessionAttr(self, connection, name):
        self.initSession(connection)
        return connection._session[name]

    def setConnectionSessionAttr(self, connection, name, val):
        self.initSession(connection)
        connection._session[name] = val
        self.saveSession(connection)
        connection.put()

    def delSessionAttr(self, connection, name):
        self.initSession(connection)
        del connection._session[name]
        self.saveSession(connection)
        connection.put()
