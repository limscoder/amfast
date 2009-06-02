"""Classes that manage connections."""
import time
import threading

from beaker.session import Session

from subscription import Subscription

class Connection(Session):
    """Stores information about connected clients.
    Uses Beaker package for persistence.
    """
 
    ACCESSED_KEY = '_last_accessed'
    ACTIVE_KEY = '_active'
    CHANNEL_KEY = '_channel'
    SUBSCRIPTION_KEY = '_subscriptions'
    MESSAGE_KEY = '_messages'

    def __init__(self, id, type=None, data_dir=None,
        timeout=None, namespace_class=None, **namespace_args):

        Session.__init__(self, {}, id=id, invalidate_corrupt=False,
            use_cookies=False, type=type, data_dir=data_dir,
            key='beaker.session.id', timeout=timeout, cookie_expires=False,
            cookie_domain=None, secret=None, secure=False,
            namespace_class=namespace_class, **namespace_args)

    def disconnect(self):
        """Disconnects this connection."""
        print "Deleting connection: '%s'." % self.id
        self.delete()

    def poll(self):
        """Returns all current messages and empties que."""
        self.lock()
        try:
            results = [self.personalizeMsg(msg[0], msg[1]) for msg in self[self.MESSAGE_KEY]]
            if len(results) > 0:
                self[self.MESSAGE_KEY] = []
                self.save()
        finally:
            self.unlock()

        return results

    def popMessage(self):
        """Remove and return a single message from the qeue."""
        self.lock()
        try:
            msg = self[self.MESSAGE_KEY].pop(0)
            self.save()
        finally:
            self.unlock()

        return self.personalizeMsg(msg[0], msg[1])

    def hasMessages(self):
        """Returns True if messages are present."""
        return len(self[self.MESSAGE_KEY]) > 0

    def personalizeMsg(self, msg, client_id):
        """Returns a copy of the msg with the clientId set."""
        return msg.__class__(headers=msg.headers, body=msg.body,
            timeToLive=msg.timeToLive, clientId=client_id,
            destination=msg.destination, timestamp=msg.timestamp)

    def publish(self, msg, client_id):
        """Add a message to the connection's message qeue.

        arguments
        ==========
         * msg, AbstractMessage, message to publish.
         * client_id, string, client id this message is being published for.
        """
        self.lock()
        try:
            self.load() # Make sure other published messages are included.
            self[self.MESSAGE_KEY].append((msg, client_id))
            self.save()
        finally:
            self.unlock()

    def subscribe(self, client_id, topic):
        """Subscribe to a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to subscribe to.
        """
        subscription = Subscription(self.id, client_id, topic)

        self.lock()
        try:
            subscriptions = self.get(self.SUBSCRIPTION_KEY, None)
            if subscriptions is None:
                subscriptions = {} 
                self[self.SUBSCRIPTION_KEY] = subscriptions

            client_subscriptions = subscriptions.get(client_id, None)
            if client_subscriptions is None:
                client_subscriptions = {}
                subscriptions[client_id] = client_subscriptions

            client_subscriptions[topic] = subscription
            self.save()
        finally:
            self.unlock()

        return subscription

    def unsubscribe(self, client_id, topic):
        """Un-Subscribe from a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to un-subscribe from.
        """

        self.lock()
        try:
            subscriptions = self.get(self.SUBSCRIPTION_KEY, None)
            if subscriptions is not None:
                client_subscriptions = subscriptions.get(client_id, None)
                if client_subscriptions is None:
                    if topic in client_subscriptions:
                        del client_subscriptions[topic]
                    self.save()
        finally:
            self.unlock()

    def clean(self, current_time=None):
        """Delete old messages."""
        print "Cleaning messages"
        if current_time is None:
            current_time = time.time()

        tmp = []
        self.lock()
        try:
            for msg in self[self.MESSAGE_KEY]:
                if msg.isExpired(current_time):
                    continue
                tmp.append(msg)
            self[self.MESSAGE_KEY] = tmp
            self.save()
        finally:
            self.unlock()
