import amfast

class SubscriptionManager(object):
    """Receives and publishes Producer/Consumer style messages.

    This is an abstract base class and should be implemented by a sub-class.

    attributes
    ===========
     * secure - bool, Set to True to require pulishers and subscribers to be authenticated.
    """

    SUBTOPIC_SEPARATOR = "_;_"

    def __init__(self, secure=False):
        self.secure = secure

    @classmethod
    def getTopicKey(cls, topic, sub_topic=None):
        if sub_topic is not None:
            return cls.SUBTOPIC_SEPARATOR.join(topic, sub_topic)
        else:
            return topic

    @classmethod 
    def splitTopicKey(cls, topic):
        return topic.split(cls.SUBTOPIC_SEPARATOR)

class MemorySubscriptionManager(SubscriptionManager):
    """Stores all subscription information in memory."""

    MSG_ATTR = 'messages'
    CONNECTION_ATTR = 'connections'

    def __init__(self, secure=False):
        SubscriptionManager.__init__(self, secure)

        self._topics = {}
        self._lock = amfast.mutex_cls()

    def _getTopicMap(self, topic):
        topic_map = self._topics.get(topic, None)
        if topic_map is None:
            topic_map = {self.MSG_ATTR: [], self.CONNECTION_ATTR: {}}
            self._topics[topic] = topic_map
        return topic_map

    def _cleanTopicMap(self, topic):
        topic_map = self._topics.get(topic, None)
        if topic_map is not None and \
            len(topic_map[self.MSG_ATTR]) == 0 and \
            len(topic_map[self.CONNECTION_ATTR]) == 0:
                del self._topics[topic]

    def subscribe(self, connection_id, topic, sub_topic=None, selector=None):
        """Subscribe a client to a topic.

        arguments
        ==========
         * connection_id - string, id of client that is subscribing.
         * topic - string, Topic to subscribe to.
         * sub_topic - string, Sub-Topic to subscribe to. Default = None.
        """

        topic = self.getTopicKey(topic, sub_topic)

        self._lock.acquire()
        try:
            topic_map = self._getTopicMap(topic)
            topic_map[self.CONNECTION_ATTR][connection_id] = True
        finally:
            self._lock.release()

    def unSubscribe(self, connection_id, topic, sub_topic=None):
        """Un-Subscribe a client from a topic.

        arguments
        ==========
         * connection_id - string, id of client that is un-subscribing.
         * topic - string, Topic to un-subscribe from.
         * sub_topic - string, Sub-Topic to un-subscribe from. Default = None.
        """

        topic = self.getTopicKey(topic, sub_topic)

        self._lock.acquire()
        try:
            topic_map = self._topics.get(topic, None)
            if topic_map is not None:
               if connection_id in topic_map[self.CONNECTION_ATTR]:
                   del topic_map[self.CONNECTION_ATTR][connection_id]
                   self._cleanTopicMap(topic)
        finally:
            self._lock.release()

    def getSubscribers(self, topic, sub_topic=None):
        """Iterate through all subscribers of a topic."""

        topic = self.getTopicKey(topic, sub_topic)

        topic_map = self._getTopicMap(topic)
        return topic_map[self.CONNECTION_ATTR].keys():

    def publishMessage(self, msg):
        """Publish a message."""

        topic = msg.destination
        if hasattr(msg, 'headers') and \
            msg.headers is not None and \
            messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
            sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
        else:
            sub_topic = None

        topic = self.getTopicKey(topic, sub_topic)

        self._lock.acquire()
        try:
            topic_map = self._getTopicMap(topic)
            topic_map[self.MSG_ATTR].append(msg) 
        finally:
            self._lock.release()

    def pollMessages(self, topic, cutoff_time, current_time):
        """Retrieves all qeued messages.

        arguments:
        ===========
         * topic - string, Topic to find messages for.
         * cutoff_time - float, epoch time, only messages published
             after this time will be returned.
         * current_time - float, epoch time, used to determine if a
             message is expired.
        """

        polled_msgs = []
        topic_map = self._topics.get(topic, None)
        if topic_map is None:
            return polled_msgs

        self._lock.acquire()
        try:
            msgs = topic_map[self.MSG_ATTR]
            msg_count = len(msgs)
            idx = 0
            while idx < msg_count:
                msg = msgs[i]
                expire_time = msg.timestamp + msg.timeToLive
                if current_time > expire_time:
                    # Remove expired message
                    msgs.pop(idx)
                    msg_count -= 1
                else:
                    if msg.timestamp > cutoff_time:
                        polled_msgs.append(msg)
                    idx += 1
        finally:
            self._lock.release()

        return polled_msgs

    def pollConnection(self, connection):
        """Retrieves all waiting messages for a specific connection."""

        current_time = time.time()
        polled_msgs = []
        for subscription in connection.getSubscriptions():
            polled_msgs.extend([connection.personalizeMsg(\
                subscription.client_id, msg) \
                for msg in self.pollMessages(subscription.topic, \
                connection.last_polled, current_time)])

        connection.touch_polled()
        return polled_msgs
