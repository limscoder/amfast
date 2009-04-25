import uuid
import time
import threading

import amfast.remoting.flex_messages as messaging

class MessageAgent(object):
    """Publishes messages."""

    SUBTOPIC_SEPARATOR = "_;_"

    def __init__(self):
        self._topics = {} # Messages will be published by topic
        self._clients = {} # Messages will be retrieved by client
        self.clientId = str(uuid.uuid4()) # MessageAgent clientId

    def subscribe(self, connection, client_id, topic,
        sub_topic=None, selector=None):
        """Subscribe a client to a topic and channel."""

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        lock = threading.RLock()
        lock.acquire()
        try:
            topic_map = self._topics.get(topic, None)
            if topic_map is None:
                topic_map = {}
                self._topics[topic] = topic_map

            connection.subscribe(client_id, topic)
            topic_map[client_id] = connection
        finally:
            lock.release()

    def unsubscribe(self, connection, client_id, topic,
        sub_topic=None, selector=None):
        """Subscribe a client from a topic."""

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        lock = threading.RLock()
        lock.acquire()
        try:
            connection.unsubscribe(client_id, topic)

            topic_map = self._topics.get(topic, None)
            if topic_map is not None:
               del topic_map[client_id]

               if len(topic_map) < 1:
                   del self._topics[topic]
        finally:
            lock.release()

    def publish(self, body, topic, sub_topic=None, client_id=None, ttl=600):
        """Publish a message."""

        current_time = int(time.time() * 1000)
        ttl *= 1000

        connections = {}
        if client_id is not None:
            if client_id in self._clients:
                connections = {client_id: self._clients[client_id]}
        else:
            if sub_topic is not None:
                com_topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))
            else:
                com_topic = topic
               
            if com_topic in self._topics:
                connections = self._topics[com_topic]

        for client_id, connection in connections.iteritems():
            headers = None
            if sub_topic is not None:
                headers = {messaging.AsyncMessage.SUBTOPIC_HEADER: sub_topic}

            msg = messaging.AsyncMessage(headers=headers, body=body,
                clientId=client_id, destination=topic, timestamp=current_time,
                timeToLive=ttl)

            connection.publish(msg)

class Subscription(object):
    """An individual subscription to a topic."""

    def __init__(self, connection, client_id, topic):
        self.connection = connection
        self.client_id = client_id
        self.topic = topic
