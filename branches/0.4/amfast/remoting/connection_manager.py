import time
import uuid

import amfast
from connection import Connection, ConnectionError
import flex_messages as messaging

class NotConnectedError(ConnectionError):
    pass

class ConnectionManager(object):
    """Keeps track of all current connections.

    This is an abstract base class and should be 
    implemented by a sub-class.

    """

    def __init__(self, connection_class=Connection, connection_params=None):
        self.connection_class = connection_class
        if connection_params is None:
            connection_params = {}
        self.connection_params = connection_params

    def generateId(self):
        """Generates a unique ID for a connection."""
        return str(uuid.uuid4())

    def getConnection(self, connection_id, touch=True):
        """Retrieve an existing connection.

        arugments
        ==========
         * connection_id - string, id of client to get connection for.
             connection_id should be unique for each Flash client (flex_client_id).
         * touch - boolean, If True set 'last_accessed' to now.

        raises
        =======
         * NotConnectedError if connection doesn't exist.
        """
        if connection_id is None:
            raise NotConnectedError("Blank connection_id is not connected.")

        connection = self.loadConnection(connection_id)

        # Check for timeout
        current_time = time.time() * 1000
        if connection.last_active < (current_time - connection.timeout):
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        if touch is True:
            self.touchConnection(connection)

        return connection

    def createConnection(self, channel, connection_id=None):
        """Returns a new connection object."""
        if connection_id is None:
            connection_id = self.generateId()

        connection = self.connection_class(self, channel.name, connection_id, **self.connection_params)
        self.initConnection(connection)
        return connection

    def deleteConnection(self, connection):
        if hasattr(connection, 'notify_func') and \
            connection.notify_func is not None:
            # Call notify function,
            # which should check for
            # a disconnection.
            connection.notify_func()

        connection.unSetNotifyFunc()

    def setNotifyFunc(self, connection, func):
        raise ConnectionError('Not implemented')

    def unSetNotifyFunc(self, connection):
        raise ConnectionError('Not implemented')

class MemoryConnectionManager(ConnectionManager):
    """Manages connections in memory."""

    def __init__(self, connection_class=Connection, connection_params=None):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

        self._connections = {} # Currently connected clients
        self._lock = amfast.mutex_cls()

    def loadConnection(self, connection_id):
        connection = self._connections.get(connection_id, None)
        if connection is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        return connection

    def createConnection(self, channel, connection_id=None):
        connection = ConnectionManager.createConnection(self, channel, connection_id)
        connection._session = {}
        self._connections[connection.id] = connection
        return connection

    def initConnection(self, connection):
        connection._connected = True
        connection._last_active = time.time() * 1000
        connection._last_polled = 0.0
        connection._authenticated = False
        connection._flex_user = None

    def iterConnectionIds(self):
        return self._connections.keys()

    # --- proxies for connection properties --- #

    def getConnected(self, connection):
        return connection._connected

    def getLastActive(self, connection):
        return connection._last_active

    def getLastPolled(self, connection):
        return connection._last_polled

    def getAuthenticated(self, connection):
        return connection._authenticated

    def getFlexUser(self, connection):
        return connection._flex_user

    def getNotifyFunc(self, connection):
        if not hasattr(connection, '_notify_func_id'):
            return None
        else:
            return connection._getNotifyFuncById(connection._notify_func_id)

    # --- proxies for connection methods --- #

    def deleteConnection(self, connection):
        self._lock.acquire()
        try:
            if connection.id in self._connections:
                del self._connections[connection.id]

            connection._connected = False
        finally:
            self._lock.release()

        ConnectionManager.deleteConnection(self, connection)

    def touchConnection(self, connection):
        connection._last_active = time.time() * 1000

    def touchPolled(self, connection):
        connection._last_polled = time.time() * 1000

    def authenticateConnection(self, connection, user):
        connection._authenticated = True
        connection._flex_user = user

    def unAuthenticateConnection(self, connection):
        connection._authenticated = False
        if hasattr(connection, '_flex_user'):
            del connection._flex_user

    def setNotifyFunc(self, connection, func):
        connection._notify_func_id = connection._setNotifyFunc(func)

    def unSetNotifyFunc(self, connection):
        if hasattr(connection, '_notify_func_id'):
            connection._delNotifyFunc(connection._notify_func_id)
            del connection._notify_func_id

    def getConnectionSessionAttr(self, connection, name):
        return connection._session[name]

    def setConnectionSessionAttr(self, connection, name, val):
        connection._session[name] = val

    def delConnectionSessionAttr(self, connection, name):
        del connection._session[name]
