import uuid
import time
import threading

import amfast.remoting.flex_messages as messaging

class MessageAgent(object):
    """Publishes messages."""

    SUBTOPIC_SEPARATOR = "_;_"

    def __init__(self, secure=False):
        self.secure = secure
        self._topics = {} # Messages will be published by topic
        self._clients = {} # Messages will be retrieved by client

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
        sub_topic=None, selector=None, _disconnect=False):
        """Un-Subscribe a client from a topic."""

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        lock = threading.RLock()
        lock.acquire()
        try:
            if _disconnect is True:
                connection.unsubscribe(client_id, topic)

            topic_map = self._topics.get(topic, None)
            if topic_map is not None:
               del topic_map[client_id]

               if len(topic_map) < 1:
                   del self._topics[topic]
        finally:
            lock.release()

    def publish(self, body, topic, sub_topic=None, client_id=None, ttl=600):
        """Publish a message.

        arguments:
        ===========
        body - AbstractMessage or object.
        topic - string, the topic to publish to.
        sub_topic - string, the sub topic to publish to. Default = None
        client_id - string, if provided, only publish to specific client. Default = None
        ttl - int time to live in secoded. Default = 600
        """

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

        # Get msg properties
        if isinstance(body, messaging.AbstractMessage):
            msg_class = body.__class__
            headers = body.headers
            body = body.body
        else:
            msg_class = messaging.AsyncMessage
            headers = None
        
        if sub_topic is not None:
            if headers is None:
                headers = {}
            headers[messaging.AsyncMessage.SUBTOPIC_HEADER] = sub_topic

        for client_id, connection in connections.iteritems():
            msg = msg_class(headers=headers, body=body,
                clientId=client_id, destination=topic, timestamp=current_time,
                timeToLive=ttl)

            connection.publish(msg)
