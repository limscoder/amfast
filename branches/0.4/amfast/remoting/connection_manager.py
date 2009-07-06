import time
import uuid

import amfast
from connection import Connection, ConnectionError

class NotConnectedError(ConnectionError):
    pass

class TimeOutError(ConnectionError):
    pass

class ConnectionManager(object):
    """Keeps track of all current connections."""

    def __init__(self, timeout=3600,
        storage_type='memory', data_dir=None,
        namespace_class=None, namespace_args=None):
    
        self.timeout = timeout
        self.storage_type = storage_type
        self.data_dir = data_dir
        self.namespace_class = namespace_class

        if namespace_args is None:
            namespace_args = {}
        self.namespace_args = namespace_args

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
        connection = Connection(connection_id, storage_type=self.storage_type,
            data_dir=self.data_dir, timeout=self.timeout,
            namespace_class=self.namespace_class, **self.namespace_args)

        if connection.is_new is True:
            connection.delete()
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        cutoff_time = time.time() - self.timeout
        if connection.last_active < cutoff_time:
            connection.delete()
            raise TimeOutError("Connection '%s' is timed out." % connection_id)

        if touch is True:
            connection.last_active = time.time()

        return connection

    def createConnection(self, connection_id=None):
        """Returns a new connection object."""
        if connection_id is None:
            connection_id = self.generateId()

        connection = Connection(connection_id, storage_type=self.storage_type,
            data_dir=self.data_dir, timeout=self.timeout,
            namespace_class=self.namespace_class, **self.namespace_args)

        connection.last_active = time.time()
        return connection

    def deleteConnection(self, connection):
        connection.delete()

class MemoryConnectionManager(ConnectionManager):
    """Manages connections in memory."""

    def __init__(self, *args, **kwargs):
        ConnectionManager.__init__(self, *args, **kwargs)
        self._connections = {} # Currently connected clients
        self._lock = amfast.mutex_cls()

    def createConnection(self, connection_id=None):
        connection = ConnectionManager.createConnection(self, connection_id)
        self._connections[connection.id] = True
        return connection

    def deleteConnection(self, connection):
        self._lock.acquire()
        try:
            id = connection.id
            connection.delete()
            if id in self._connections:
                del self._connections[id]
        finally:
            self._lock.release()

    def getConnectionIds(self):
        return self._connections.keys()
