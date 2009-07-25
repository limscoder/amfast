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
     * timeout - int, timeout in milliseconds
     * connected - boolean, True if connection is connected
     * last_active - float, epoch timestamp when connection was last accessed.
     * last_polled - float, epocj timestamp when connection last polled for messsages.
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

    def __init__(self, manager, channel_name, id, timeout=1800000):
        self._manager = manager
        self._channel_name = channel_name
        self._id = id
        self._timeout = timeout
        self._connected = True
        self._last_active = time.time() * 1000
        self._last_polled = 0.0
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

    def _getLastPolled(self):
        return self._last_polled
    last_polled = property(_getLastPolled)

    def _getAuthenticated(self):
        return self._authenticated
    authenticated = property(_getAuthenticated)

    def _getFlexUser(self):
        return self._flex_user
    flex_user = property(_getFlexUser)

    def _getNotifyFunc(self):
        if not hasattr(self, '_notify_func_id'):
            return None
        return self._getNotifyFuncById(self._notify_func_id)
    notify_func = property(_getNotifyFunc)

    # These methods are just proxies to the manager's methods
    def touch(self):
        """Update last_active."""
        self._manager.touchConnection(self)

    def touch_polled(self):
        """Update last_polled."""
        self._manager.touchPolled(self)

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
