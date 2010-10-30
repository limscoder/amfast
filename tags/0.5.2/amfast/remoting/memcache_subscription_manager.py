import memcache_manager
from subscription_manager import Subscription, SubscriptionManager
import flex_messages as messaging

class MemcacheSubscriptionManager(SubscriptionManager, memcache_manager.MemcacheManager):
    """Stores all subscription information in memcache."""

    TOPIC_ATTR = '_topics'
    MSG_ATTR = '_messages'
    CONNECTION_ATTR = '_connections'

    def __init__(self, secure=False, ttl=30000, mc_servers=['127.0.0.1:11211'], mc_debug=0):
        SubscriptionManager.__init__(self, secure=secure, ttl=ttl)

        self.mc = self.createMcClient(mc_servers, mc_debug)
        self._lock = memcache_manager.MemcacheMutex(self.mc)

    def reset(self):
        self._lock.releaseAll()

        lock_name = self.getLockName('subscription_reset')
        self._lock.acquire(lock_name)
        try:
            topics = self.mc.get(self.TOPIC_ATTR)
            if topics is not None:
                for topic in topics.iterkeys():

                    msg_key = self.getKeyName(topic, self.MSG_ATTR)
                    self.mc.delete(msg_key)

                    connection_key = self.getKeyName(topic, self.CONNECTION_ATTR)
                    connections = self.mc.get(connection_key)
                    for connection_id in connections:
                        key = self.getKeyName(connection_id, topic)
                        self.mc.delete(key)
               
                    self.mc.delete(connection_key)
                self.mc.set(self.TOPIC_ATTR, {})
        finally:
            self._lock.release(lock_name)

    def _cleanTopic(self, topic):
        """Removes un-needed subscription data for a topic."""

        msg_key = self.getKeyName(topic, self.MSG_ATTR)
        msgs = self.mc.get(msg_key)

        connection_key = self.getKeyName(topic, self.CONNECTION_ATTR)
        connections = self.mc.get(connection_key)

        if (msgs is None or len(msgs) == 0) and \
            (connections is None or len(connections) == 0):

            lock_name = self.getLockName(self.TOPIC_ATTR)
            self._lock.acquire(lock_name)
            try:
                topics = self.mc.get(self.TOPIC_ATTR)
                if topic in topics:
                    del topics[topic]
                    self.mc.set(self.TOPIC_ATTR, topics)

                if msgs is not None:
                    self.mc.delete(msg_key)

                if connections is not None:
                    self.mc.delete(connection_key)
            finally:
                self._lock.release(lock_name)

    def _createTopic(self, topic):
        lock_name = self.getLockName(self.TOPIC_ATTR)
        self._lock.acquire(lock_name)
        try:
            topics = self.mc.get(self.TOPIC_ATTR)
            if topics is None:
                topics = {}
            topic_map = topics.get(topic, None)
            if topic_map is None:
                topics[topic] = True
                self.mc.set(self.TOPIC_ATTR, topics)
        finally:
            self._lock.release(lock_name)

    def _createTopicMessageQeue(self, topic):
        key = self.getKeyName(topic, self.MSG_ATTR)
        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            messages = self.mc.get(key)
            if messages is None:
                self.mc.set(key, [])
        finally:
            self._lock.release(lock_name)

    def _createConnectionList(self, topic, connection_id):
        key = self.getKeyName(topic, self.CONNECTION_ATTR)
        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            connections = self.mc.get(key)
            if connections is None:
                connections = {}

            connections[connection_id] = True
            self.mc.set(key, connections)
        finally:
            self._lock.release(lock_name)

    def _createClientList(self, topic, connection_id, client_id, subscription):
        key = self.getKeyName(connection_id, topic)
        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            connection_map = self.mc.get(key)
            if connection_map is None:
                connection_map = {}

            connection_map[client_id] = subscription
            self.mc.set(key, connection_map)
        finally:
            self._lock.release(lock_name)

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

        self._createTopic(topic)
        self._createTopicMessageQeue(topic)
        self._createConnectionList(topic, connection_id)
        self._createClientList(topic, connection_id, client_id, subscription)

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

        key = self.getKeyName(connection_id, topic)
        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            connection_map = self.mc.get(key)
            if connection_map is None:
                # Connection has already been removed.
                return
            elif len(connection_map) == 1:
                # This is the only subscribed client.
                # Delete client list.
                self.mc.delete(key)

                # Delete connection_id from subscription list
                sub_key = self.getKeyName(topic, self.CONNECTION_ATTR)
                sub_lock_name = self.getLockName(sub_key)
                self._lock.acquire(sub_lock_name)
                try:
                    connections = self.mc.get(sub_key)
                    if connection_id in connections:
                        del connections[connection_id]
                        self.mc.set(sub_key, connections)
                finally:
                    self._lock.release(sub_lock_name)

                self._cleanTopic(topic)
            else:
                # Delete single client subscription
                if client_id in connection_map:
                    del connection_map[client_id]
                    self.mc.set(key, connection_map)
        finally:
            self._lock.release(lock_name)

    def deleteConnection(self, connection):
        """Remove all subscriptions for this connection.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
        """

        # Get all subscribed topics
        topics = self.mc.get(self.TOPIC_ATTR)
        for topic in topics.iterkeys():
            # Check if connection is subscribed to a topic. 
            key = self.getKeyName(connection.id, topic)
            if self.mc.get(key) is not None:
                # Connection is subscribed to this topic
                self.mc.delete(key)
          
                # Delete connection_id from subscription list
                sub_key = self.getKeyName(topic, self.CONNECTION_ATTR)
                sub_lock_name = self.getLockName(sub_key)
                self._lock.acquire(sub_lock_name)
                try:
                    connections = self.mc.get(sub_key)
                    if connection.id in connections:
                        del connections[connection.id]
                        self.mc.set(sub_key, connections)
                    self._cleanTopic(topic)
                finally:
                    self._lock.release(sub_lock_name)

    def iterSubscribers(self, topic, sub_topic=None):
        """Iterate through Flash client ids subscribed to a specific topic."""

        topics = self.mc.get(self.TOPIC_ATTR)
        for topic in topics.iterkeys():
            key = self.getKeyName(topic, self.CONNECTION_ATTR)
            connections = self.mc.get(key)
            for connection_id in connections.iterkeys():
                yield connection_id

    def iterConnectionSubscriptions(self, connection):
        """Iterate through all Subscriptions that belong to a specific connection."""

        # Get all subscribed topics
        topics = self.mc.get(self.TOPIC_ATTR)
        for topic in topics.iterkeys():
            # Check if connection is subscribed to a topic. 
            key = self.getKeyName(connection.id, topic)
            subscriptions = self.mc.get(key)
            if subscriptions is not None:
                for subscription in subscriptions.itervalues():
                    yield subscription

    def persistMessage(self, msg):
        """Store a message."""

        topic = msg.destination
        if hasattr(msg, 'headers') and \
            msg.headers is not None and \
            messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
            sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
        else:
            sub_topic = None
        topic = self.getTopicKey(topic, sub_topic)

        # Remove connection data,
        # so that it is not pickled
        tmp_connection = getattr(msg, 'connection', None)
        if tmp_connection is not None:
            msg.connection = None

        key = self.getKeyName(topic, self.MSG_ATTR)
        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            messages = self.mc.get(key)
            if messages is None:
                messages = [] 
            messages.append(msg)
            self.mc.set(key, messages)
        finally:
            self._lock.release(lock_name)

            # Restore connection data
            if tmp_connection is not None:
                msg.connection = tmp_connection

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

        key = self.getKeyName(topic, self.MSG_ATTR)
        lock_name = self.getLockName(key)
        self._lock.acquire(lock_name)
        try:
            msgs = self.mc.get(key)
            if msgs is None:
                return

            msg_count = len(msgs)
            set = False
            idx = 0
            while idx < msg_count:
                msg = msgs[idx]
                if current_time > (msg.timestamp + msg.timeToLive):
                    # Remove expired message
                    msgs.pop(idx)
                    msg_count -= 1
                    set = True
                else:
                    idx += 1
                    if msg.timestamp > cutoff_time:
                        yield msg

            if set is True:
                self.mc.set(key, msgs)
        finally:
            self._lock.release(lock_name)
