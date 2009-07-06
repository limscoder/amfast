import amfast

class SubscriptionManager(object):
    """Receives and publishes Producer/Consumer style messages.

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

    def __init__(self, secure=False):
        SubscriptionManager.__init__(self, secure)

        self._topics = {}
        self._lock = amfast.mutex_cls()

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
            topic_map = self._topics.get(topic, None)
            if topic_map is None:
                topic_map = {}
                self._topics[topic] = topic_map

            topic_map[connection_id] = True
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
               if connection_id in topic_map:
                   del topic_map[connection_id]

               if len(topic_map) < 1:
                   del self._topics[topic]
        finally:
            self._lock.release()

    def getSubscribers(self, topic, sub_topic=None):
        """Iterate through all subscribers of a topic."""

        topic = self.getTopicKey(topic, sub_topic)

        topic_map = self._topics.get(topic, None)
        if topic_map is None:
            return 

        for connection_id in topic_map.keys():
            yield connection_id
