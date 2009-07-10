import time

from beaker.session import Session

import amfast
import flex_messages as messaging
from subscription_manager import SubscriptionManager

class ConnectionError(amfast.AmFastError):
    pass

class Connection(Session):
    """A client connection to a Channel.

    This class acts like a session.
    Unique to a single flash client.
    Persisted by Beaker package.

    attributes
    ============
     * last_active - float, epoch timestamp when connection was last accessed.
     * authenticated - boolean, True if connection has been authenticated with RemoteObject style authentication.
     * flex_user - string, username if 'authenticated' is True.
     * subscriptions - dict, subscribed topics
     * channel_name - string, name of the channel connection is connected to.

    """

    def __init__(self, id, beaker_params=None):

        beaker_defaults = {
            'type': 'memory',
            'timeout': 1800,
            'invalidate_corrupt': False,
            'use_cookies': False,
            'secure': False
        }

        if beaker_params is not None:
            beaker_defaults.extend(beaker_params)

        Session.__init__(self, {}, id=id, **beaker_defaults)

        if self.is_new:
            self._c_loaded = True
            self._c_dirty = True
            self._init()
        else:
            self._c_loaded = False
            self._c_dirty = False

    def __getitem__(self, key):
        """Lazy-load session when item is accessed."""
        if self._c_loaded is False:
            self.load()
        return Session.__getitem__(self, key)

    def __setitem__(self, key, value):
        """Mark as dirty, so save is implemented properly."""
        if self._c_loaded is False:
            self.load()
        self._c_dirty = True
        Session.__setitem__(self, key, value)

    def __delitem__(self, key):
        """Mark as dirty, so save is implemented properly."""
        if self._c_loaded is False:
            self.load()
        self._c_dirty = True
        Session.__delitem__(self, key)

    def _init(self):
        """Initialize new connections."""
        self.authenticated = False
        self.subscriptions = {}

    LAST_ACTIVE = '_LAST_ACTIVE'
    def _getLastActive(self):
        return self[self.LAST_ACTIVE]

    def _setLastActive(self, val):
        self[self.LAST_ACTIVE] = val

    def _delLastActive(self):
        del self[self.LAST_ACTIVE]
    last_active = property(_getLastActive, _setLastActive, _delLastActive)

    AUTHENTICATED = '_AUTHENTICATED'
    def _getAuthenticated(self):
        return self[self.AUTHENTICATED]

    def _setAuthenticated(self, val):
        self[self.AUTHENTICATED] = val

    def _delAuthenticated(self):
        del self[self.AUTHENTICATED]
    authenticated = property(_getAuthenticated, _setAuthenticated, _delAuthenticated)

    FLEX_USER = '_FLEX_USER'
    def _getFlexUser(self):
        return self[self.FLEX_USER]

    def _setFlexUser(self, val):
        self[self.FLEX_USER] = val

    def _delFlexUser(self):
        del self[self.FLEX_USER]
    flex_user = property(_getFlexUser, _setFlexUser, _delFlexUser)

    SUBSCRIPTIONS = '_SUBSCRIPTIONS'
    def _getSubscriptions(self):
        return self[self.SUBSCRIPTIONS]

    def _setSubscriptions(self, val):
        self[self.SUBSCRIPTIONS] = val

    def _delSubscriptions(self):
        del self[self.SUBSCRIPTIONS]
    subscriptions = property(_getSubscriptions, _setSubscriptions, _delSubscriptions)

    CHANNEL_NAME = '_CHANNEL_NAME'
    def _getChannelName(self):
        return self[self.CHANNEL_NAME]

    def _setChannelName(self, val):
        self[self.CHANNEL_NAME] = val

    def _delChannelName(self):
        del self[self.CHANNEL_NAME]
    channel_name = property(_getChannelName, _setChannelName, _delChannelName)

    NOTIFY_KEY = '_NOTIFY_KEY'
    def _getNotifyKey(self):
        return self[self.NOTIFY_KEY]

    def _setNotifyKey(self, val):
        self[self.NOTIFY_KEY] = val

    def _delNotifyKey(self):
        del self[self.NOTIFY_KEY]
    notify_key = property(_getNotifyKey, _setNotifyKey, _delNotifyKey)

    def load(self):
        """Load connection details."""
        self._c_loaded = True
        Session.load(self)

    def save(self, force=False):
        """Save connection details."""
        if self._c_dirty is True or force is True:
            self._c_loaded = True
            self._c_dirty = False
            Session.save(self)

    def subscribe(self, client_id, topic, sub_topic=None):
        """Add a subscription to a topic."""
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        self.lock()
        try:
            topic_map = self.subscriptions.get(topic, None)
            if topic_map is None:
                topic_map = {}
                self.subscriptions[topic] = topic_map

            if client_id not in topic_map:
                topic_map[client_id] = []
        finally:
            self.unlock()

    def getSubscribedTopics(self):
        """Returns a list of topics that the connection is subscribed to."""
        return self.subscriptions.keys()

    def getSubscribedClients(self, topic, sub_topic=None):
        """Returns a list of client_ids subscribed to topic."""
        client_ids = []
        topic_map = self.subscriptions.get(topic, None)
        if topic_map is None:
            return client_ids
        else:
            return topic_map.keys()
        
    def unSubscribe(self, client_id, topic, sub_topic=None):
        """Remove a subscription from a topic."""
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        self.lock()
        try:
            topic_map = self.subscriptions.get(topic, None)
            if topic_map is None:
                topic_map = {}
                self.subscriptions[topic] = topic_map

            if client_id in topic_map:
                del topic_map[client_id]

                if len(topic_map) < 1:
                    del self.subscriptions[topic]
        finally:
            self.unlock()

    def publishMessage(self, msg):
        """Publish a message to this connection.

        The message will be published to all suscribed MessageAgents.
 
        arguments:
        ===========
         * msg - AbstractMessage, the message to publish.
        """

        topic = msg.destination
        if hasattr(msg, 'headers') and \
            msg.headers is not None and \
            messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
            sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
        else:
            sub_topic = None

        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        self.lock()
        self.load()
        try:
            topic_map = self.subscriptions.get(topic, None)
            if topic_map is None:
                return

            for messages in topic_map.itervalues():
                messages.append(msg)
            self.save(force=True)
        finally:
            self.unlock()

    def hasMessages(self):
        """Returns True if new messages are present."""
        for topic_map in self.subscriptions.values():
            for messages in topic_map.values():
                if len(messages) > 0:
                    return True

        return False

    def poll(self):
        """Returns a list of messages, and clears message qeue."""

        polled_messages = []

        self.lock()
        self.load()
        try:
            for topic_map in self.subscriptions.itervalues():
                for client_id, messages in topic_map.iteritems():
                    for i in xrange(len(messages)):
                        polled_messages.append(self.personalizeMessage(client_id, messages.pop()))
            self.save(force=True)
        finally:
            self.unlock()

        return polled_messages

    def personalizeMessage(self, client_id, msg):
        """Return a copy of the message with client_id set."""
        if hasattr(msg, 'headers'):
            headers = msg.headers
        else:
            headers = None

        return msg.__class__(headers=headers, body=msg.body,
            timeToLive=msg.timeToLive, clientId=client_id,
            destination=msg.destination, timestamp=msg.timestamp)
