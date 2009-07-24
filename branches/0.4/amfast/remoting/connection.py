import time

import amfast
import flex_messages as messaging

class ConnectionError(amfast.AmFastError):
    pass

class Connection(object):
    """A client connection to a Channel.

    This class acts like a session.
    Unique to a single flash client.

    attributes (read-only)
    =======================
     * manager - ConnectionManager, the class that manages connection persistence.
     * channel_name - string, name of the channel connection is connected to.
     * id - string, Flash client's ID.
     * timeout - int, timeout in seconds
     * connected - boolean, True if connection is connected
     * last_active - float, epoch timestamp when connection was last accessed.
     * authenticated - boolean, True if connection has been authenticated with RemoteObject style authentication.
     * flex_user - string, username if 'authenticated' is True.

    """

    # Keeps track of notification functions
    # by their IDs, 
    # so they can be serialized
    # when the connection is saved.
    _notifications = {}

    @classmethod
    def _setNotifyFunc(cls, func):
        func_id = id(func)
        cls._notifications[func_id] = func
        return func_id

    @classmethod
    def _getNotifyFuncById(cls, func_id):
        return cls._notifications[func_id]

    @classmethod
    def _delNotifyFunc(cls, func_id):
        del cls._notifications[func_id]

    def __init__(self, manager, channel_name, id, timeout=1800):
        self._manager = manager
        self._channel_name = channel_name
        self._id = id
        self._timeout = timeout
        self._connected = True
        self._last_active = 0.0
        self._authenticated = False

    # These properties should all be read only!!
    def _getManager(self):
        return self._manager
    manager = property(_getManager)

    def _getChannelName(self):
        return self._channel_name
    channel_name = property(_getChannelName)

    def _getId(self):
        return self._id
    id = property(_getId)

    def _getTimeout(self):
        return self._timeout
    timeout = property(_getTimeout)

    def _getConnected(self):
        return self._connected
    connected = property(_getConnected)

    def _getLastActive(self):
        return self._last_active
    last_active = property(_getLastActive)

    def _getAuthenticated(self):
        return self._authenticated
    authenticated = property(_getAuthenticated)

    def _getFlexUser(self):
        return self._flex_user
    flex_user = property(_getFlexUser)

    def _getNotifyFunc(self):
        return self._getNotifyFuncById(self._notify_func_id)
    notify_func = property(_getNotifyFunc)

    # These methods are just proxies to the manager's methods
    def touch(self):
        """Update last_active."""
        self._manager.touchConnection(self)

    def subscribe(self, client_id, topic, sub_topic=None):
        self._manager.subscribeConnection(self, client_id, topic, sub_topic)

    def unSubscribe(self, client_id, topic, sub_topic=None):
        """Remove a subscription from a topic."""
        self._manager.unSubscribeConnection(self, client_id, topic, sub_topic)

    def publishMessage(self, msg):
        """Publish a message to this connection.

        The message will be published to all suscribed MessageAgents.
 
        arguments:
        ===========
         * msg - AbstractMessage, the message to publish.
        """
        self._manager.publishToConnection(self, msg)

    def poll(self):
        """Returns a list of messages, and clears message qeue."""
        return self._manager.pollConnection(self)

    def getSubscribedTopics(self):
        """Returns a list of topics that the connection is subscribed to."""
        return self._manager.getSubscribedTopics(self)

    def getSubscribedClients(self, topic, sub_topic=None):
        return self._manager.getSubscribedClients(self, topic, sub_topic)

    def delete(self):
        self._manager.deleteConnection(self)

    def authenticate(self, user):
        self._manager.authenticateConnection(self, user)

    def unAuthenticate(self):
        self._manager.unAuthenticateConnection(self)

    def getSessionAttr(self, name):
        self._manager.getConnectionSessionAttr(self, name)

    def setSessionAttr(self, name, val):
        self._manager.setConnectionSessionAttr(self, name, val)

    def delSessionAttr(self, name):
        self._manager.delConnectionSessionAttr(self, name)

    # Actual methods

    def setNotifyFunc(self, func):
        self._notify_func_id = self._setNotifyFunc(func)

    def unSetNotifyFunc(self):
        if hasattr(self, '_notify_func_id'):
            self._delNotifyFunc(self._notify_func_id)
            del self._notify_func_id

    def personalizeMessage(self, client_id, msg):
        """Return a copy of the message with client_id set."""
        if hasattr(msg, 'headers'):
            headers = msg.headers
        else:
            headers = None

        return msg.__class__(headers=headers, body=msg.body,
            timeToLive=msg.timeToLive, clientId=client_id,
            destination=msg.destination, timestamp=msg.timestamp)
