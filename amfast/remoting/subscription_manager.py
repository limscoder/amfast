import time

import amfast
import flex_messages as messaging

class Subscription(object):
    def __init__(self, connection_id=None, client_id=None, topic=None):
        self.connection_id = connection_id
        self.client_id = client_id
        self.topic = topic

class SubscriptionManager(object):
    """Receives and publishes Producer/Consumer style messages.

    This is an abstract base class and should be implemented by a sub-class.

    attributes
    ===========
     * secure - bool, Set to True to require pulishers and subscribers to be authenticated.
     * ttl - float, Default timeToLive in milliseconds for messages that do not have the value set.
    """

    SUBTOPIC_SEPARATOR = "_;_"

    def __init__(self, secure=False, ttl=10000):
        self.secure = secure
        self.ttl = ttl

    @classmethod
    def getTopicKey(cls, topic, sub_topic=None):
        if sub_topic is not None:
            return cls.SUBTOPIC_SEPARATOR.join((topic, sub_topic))
        else:
            return topic

    @classmethod 
    def splitTopicKey(cls, topic):
        return topic.split(cls.SUBTOPIC_SEPARATOR)

    def getMessageTopicKey(self, msg):
        """Returns topic key for a message."""

        topic = msg.destination
        if hasattr(msg, 'headers') and \
            msg.headers is not None and \
            messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
            sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
        else:
            sub_topic = None
        return self.getTopicKey(topic, sub_topic)

    def publishMessage(self, msg):
        # Update timestamp to current server time.
        # Is this the correct thing to do???
        msg.timestamp = time.time() * 1000
        if msg.timeToLive is None or msg.timeToLive == 0:
            # Set timeToLive if it has not been pre-set.
            msg.timeToLive = self.ttl

        self.persistMessage(msg)

    def pollConnection(self, connection, soft_touch=False):
        """Retrieves all waiting messages for a specific connection.

        parameters
        ===========
         * connection - Connection, connection to poll.
         * soft_touch - boolean, True to call connection.touchSoftPolled,
             False to call connection.touchPolled. Default = False

        """

        current_time = time.time() * 1000
        polled_msgs = []
        for subscription in self.iterConnectionSubscriptions(connection):
            polled_msgs.extend([connection.personalizeMessage(\
                subscription.client_id, msg) \
                for msg in self.pollMessages(subscription.topic, \
                    connection.last_polled, current_time)])

        if soft_touch is True:
            connection.softTouchPolled()
        else:
            connection.touchPolled()
        return polled_msgs

class MemorySubscriptionManager(SubscriptionManager):
    """Stores all subscription information in memory."""

    MSG_ATTR = 'messages'
    CONNECTION_ATTR = 'connections'

    def __init__(self, secure=False, ttl=30000):
        SubscriptionManager.__init__(self, secure=secure, ttl=ttl)

        self._lock = amfast.mutex_cls()
        self.reset()

    def reset(self):
        self._topics = {}

    def _getTopicMap(self, topic):
        """Retrieves or creates a topic map."""

        topic_map = self._topics.get(topic, None)
        if topic_map is None:
            topic_map = {self.MSG_ATTR: [], self.CONNECTION_ATTR: {}}
            self._topics[topic] = topic_map
        return topic_map

    def _cleanTopicMap(self, topic, topic_map):
        """Removes un-needed subscription data for a topic."""

        if len(topic_map[self.MSG_ATTR]) == 0 and \
            len(topic_map[self.CONNECTION_ATTR]) == 0:
            del self._topics[topic]

    def subscribe(self, connection_id, client_id, topic, sub_topic=None, selector=None):
        """Subscribe a client to a topic.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
         * client_id - string, id of messaging client that is subscribing.
         * topic - string, Topic to subscribe to.
         * sub_topic - string, Sub-Topic to subscribe to. Default = None.
        """

        topic = self.getTopicKey(topic, sub_topic)
        subscription = Subscription(connection_id=connection_id,
            client_id=client_id, topic=topic)

        self._lock.acquire()
        try:
            topic_map = self._getTopicMap(topic)
            connection_map = topic_map[self.CONNECTION_ATTR].get(connection_id, None)
            if connection_map is None:
                connection_map = {}
                topic_map[self.CONNECTION_ATTR][connection_id] = connection_map

            connection_map[client_id] = subscription
        finally:
            self._lock.release()

    def unSubscribe(self, connection_id, client_id, topic, sub_topic=None):
        """Un-Subscribe a client from a topic.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
         * client_id - string, id of messaging client that is subscribing.
         * topic - string, Topic to un-subscribe from.
         * sub_topic - string, Sub-Topic to un-subscribe from. Default = None.
        """

        topic = self.getTopicKey(topic, sub_topic)

        self._lock.acquire()
        try:
            topic_map = self._topics.get(topic, None)
            if topic_map is not None:
               connection_map = topic_map[self.CONNECTION_ATTR].get(connection_id, None)
               if connection_map is not None:
                   if client_id in connection_map:
                       if len(connection_map) == 1:
                           # This is the only subscribed client,
                           # delete all connection data.
                           del topic_map[self.CONNECTION_ATTR][connection_id]
                           self._cleanTopicMap(topic, topic_map) # Clean up topic data
                       else:
                           # Delete this single subscription
                           del connection_map[client_id]
        finally:
            self._lock.release()

    def deleteConnection(self, connection):
        """Remove all subscriptions for this connection.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
        """

        for topic, topic_map in self._topics.items():
            if connection.id in topic_map[self.CONNECTION_ATTR]:
                del topic_map[self.CONNECTION_ATTR][connection.id]
                self._cleanTopicMap(topic, topic_map)

    def iterSubscribers(self, topic, sub_topic=None):
        """Iterate through Flash client ids subscribed to a specific topic."""

        topic = self.getTopicKey(topic, sub_topic)
        topic_map = self._topics.get(topic, None)
        if topic_map is None:
            return [].__iter__()

        return topic_map[self.CONNECTION_ATTR].keys().__iter__()

    def iterConnectionSubscriptions(self, connection):
        """Iterate through all Subscriptions that belong to a specific connection."""

        for topic_map in self._topics.values():
            connection_map = topic_map[self.CONNECTION_ATTR].get(connection.id, {})
            for subscription in connection_map.values():
                yield subscription

    def persistMessage(self, msg):
        """Store a message."""

        topic = self.getMessageTopicKey(msg)

        self._lock.acquire()
        try:
            topic_map = self._getTopicMap(topic)
            topic_map[self.MSG_ATTR].append(msg) 
        finally:
            self._lock.release()

    def pollMessages(self, topic, cutoff_time, current_time):
        """Retrieves all queued messages, and discards expired messages.

        arguments:
        ===========
         * topic - string, Topic to find messages for.
         * cutoff_time - float, epoch time, only messages published
             after this time will be returned.
         * current_time - float, epoch time, used to determine if a
             message is expired.
        """

        topic_map = self._topics.get(topic, None)
        if topic_map is None:
            return

        self._lock.acquire()
        try:
            msgs = topic_map[self.MSG_ATTR]
            msg_count = len(msgs)
            idx = 0
            while idx < msg_count:
                msg = msgs[idx]
                if current_time > (msg.timestamp + msg.timeToLive):
                    # Remove expired message
                    msgs.pop(idx)
                    msg_count -= 1
                else:
                    idx += 1
                    if msg.timestamp > cutoff_time:
                        yield msg
        finally:
            self._lock.release()
