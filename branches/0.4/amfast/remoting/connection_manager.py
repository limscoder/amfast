import time
import uuid

import amfast
from subscription_manager import SubscriptionManager
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
        connection = self._getConnection(connection_id)

        current_time = time.time()
        if connection.last_active < current_time - connection.timeout:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        if touch is True:
            self.touchConnection(connection)

        return connection

    def createConnection(self, channel, connection_id=None):
        """Returns a new connection object."""
        if connection_id is None:
            connection_id = self.generateId()

        connection = self.connection_class(self, channel.name, connection_id, **self.connection_params)

        self.touchConnection(connection)
        return connection

    def deleteConnection(self, connection):
        if hasattr(connection, 'notify_func'):
            # Call notify function,
            # which should check for
            # a disconnection.
            connection.notify_func()

        connection.unSetNotifyFunc()

class MemoryConnectionManager(ConnectionManager):
    """Manages connections in memory."""

    def __init__(self, connection_class=Connection, connection_params=None):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

        self._connections = {} # Currently connected clients
        self._lock = amfast.mutex_cls()

    def _getConnection(self, connection_id):

        connection = self._connections.get(connection_id, None)
        if connection is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        return connection

    def createConnection(self, channel, connection_id=None):
        connection = ConnectionManager.createConnection(self, channel, connection_id)
        connection._lock = amfast.mutex_cls()
        connection._subscriptions = {}
        connection._session = {}
        self._connections[connection.id] = connection
        return connection

    def deleteConnection(self, connection):
        connection._lock.acquire()
        try:
            if connection.id in self._connections:
                del self._connections[connection.id]

            connection._connected = False
        finally:
            connection._lock.release()

        ConnectionManager.deleteConnection(self, connection)

    def getConnectionIds(self):
        return self._connections.keys()

    def touchConnection(self, connection):
        connection._last_active = time.time()

    def subscribeConnection(self, connection, client_id, topic, sub_topic=None):
        """Add a subscription to a topic."""
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        connection._lock.acquire()
        try:
            topic_map = connection._subscriptions.get(topic, None)
            if topic_map is None:
                topic_map = {}
                connection._subscriptions[topic] = topic_map

            if client_id not in topic_map:
                topic_map[client_id] = []
        finally:
            connection._lock.release()

    def unSubscribeConnection(self, connection, client_id, topic, sub_topic=None):
        """Remove a subscription from a topic."""
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        connection._lock.acquire()
        try:
            topic_map = connection._subscriptions.get(topic, None)
            if topic_map is None:
                return

            if client_id in topic_map:
                del topic_map[client_id]

                if len(topic_map) < 1:
                    del connection._subscriptions[topic]
        finally:
            connection._lock.release()

    def getSubscribedTopics(self, connection):
        """Returns a list of topics that the connection is subscribed to."""
        return connection._subscriptions.keys()

    def getSubscribedClients(self, connection, topic, sub_topic=None):
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)
        
        topic_map = connection._subscriptions.get(topic, None)
        if topic_map is None:
            return []
        else:
            return topic_map.keys()

    def publishToConnection(self, connection, msg):
        """Publish a message to a connection."""

        topic = msg.destination
        if hasattr(msg, 'headers') and \
            msg.headers is not None and \
            messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
            sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
        else:
            sub_topic = None

        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        connection._lock.acquire()
        try:
            topic_map = connection._subscriptions.get(topic, None)
            if topic_map is None:
                return

            for messages in topic_map.itervalues():
                messages.append(msg)
        finally:
            connection._lock.release()

        if hasattr(connection, 'notify_func') and connection.notify_func is not None:
            # Call notify function to dispatch messages
            # When streaming or long-polling.
            connection.notify_func()

    def pollConnection(self, connection):
        """Returns a list of messages, and clears message qeue."""
        polled_messages = []

        connection._lock.acquire()
        try:
            for topic_map in connection._subscriptions.itervalues():
                for client_id, messages in topic_map.iteritems():
                    for i in xrange(len(messages)):
                        polled_messages.append(connection.personalizeMessage(client_id, messages.pop()))
        finally:
            connection._lock.release()

        return polled_messages

    def authenticateConnection(self, connection, user):
        connection._authenticated = True
        connection._flex_user = user

    def unAuthenticateConnection(self, connection):
        connection._authenticated = False
        if hasattr(connection, '_flex_user'):
            del connection._flex_user

    def getConnectionSessionAttr(self, connection, name):
        return connection._session[name]

    def setConnectionSessionAttr(self, connection, name, val):
        connection._session[name] = val

    def delSessionAttr(self, connection, name):
        del connection._session[name]
