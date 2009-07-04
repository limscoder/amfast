import time
import threading

from beaker.session import Session

import amfast
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

    """

    def __init__(self, id, storage_type=None, data_dir=None,
        timeout=None, namespace_class=None, **namespace_args):

        Session.__init__(self, {}, id=id, invalidate_corrupt=False,
            use_cookies=False, type=storage_type, data_dir=data_dir,
            key='beaker.session.id', timeout=timeout, cookie_expires=False,
            cookie_domain=None, secret=None, secure=False,
            namespace_class=namespace_class, **namespace_args)

        self.load()

        if self.is_new:
            self._init()

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
