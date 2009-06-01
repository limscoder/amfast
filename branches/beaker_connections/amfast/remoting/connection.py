"""Classes that manage connections."""
import threading

from beaker.session import Session

from subscription import Subscription

class Connection(Session):
    """Stores information about connected clients.
    Uses Beaker package for persistence.
    """
 
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
            namespace_class=None, **namespace_args)

    def disconnect(self):
        """Disconnects this connection."""
        self[self.ACTIVE_KEY] = False
        #self[self.CHANNEL_KEY] channel.disconnect(self)

    def poll(self):
        """Returns all current messages and empties que."""
        results = self[self.MESSAGE_KEY]
        self[self.MESSAGE_KEY] = []

        #results = tuple(self[self.MESSAGE_KEY])
        #del self[self.MESSAGE_KEY][:]
        self.save()

        return results

    def popMessage(self):
        """Remove and return a single message from the qeue."""
        result = self[self.MESSAGE_KEY].pop(0)
        self.save()

        return result

    def hasMessages(self):
        """Returns True if messages are present."""
        return len(self[self.MESSAGE_KEY]) > 0

    def publish(self, msg):
        """Add a message to the connection's message qeue.

        arguments
        ==========
         * msg, AbstractMessage, message to publish.
        """
        print "Publish id: %s:%s" % (self.id, id(self.namespace.dictionary))
        self[self.MESSAGE_KEY].append(msg)
        self.save()

    def subscribe(self, client_id, topic):
        """Subscribe to a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to subscribe to.
        """
        subscription = Subscription(self.id, client_id, topic)

        subscriptions = self.get(self.SUBSCRIPTION_KEY, None)
        if subscriptions is None:
            subscriptions = {} 
            self[self.SUBSCRIPTION_KEY] = subscriptions
            self.save()

        client_subscriptions = subscriptions.get(client_id, None)
        if client_subscriptions is None:
            client_subscriptions = {}
            subscriptions[client_id] = client_subscriptions
            self.save()

        client_subscriptions[topic] = subscription
        self.save()
        return subscription

    def unsubscribe(self, client_id, topic):
        """Un-Subscribe from a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to un-subscribe from.
        """

        subscriptions = self.get(self.SUBSCRIPTION_KEY, None)
        if subscriptions is not None:
            client_subscriptions = subscriptions.get(client_id, None)
            if client_subscriptions is None:
                if topic in client_subscriptions:
                    del client_subscriptions[topic]
                    self.save()
