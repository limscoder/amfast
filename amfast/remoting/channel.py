"""Send and receive AMF messages."""
import time
import uuid

import threading

import amfast
from amfast import AmFastError
from amfast.encoder import Encoder
from amfast.decoder import Decoder
from amfast.class_def import ClassDefMapper
from amfast.remoting import ServiceMapper, RemotingError
import amfast.remoting.flex_messages as messaging

class ChannelError(RemotingError):
    pass

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
        """Subscribe a client to a topic and channel."""

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        lock = threading.RLock()
        lock.acquire()
        try:
            connection.unsubscribe(client_id, topic)

            topic_map = self._topics.get(topic, None)
            if topic_map is not None:
               del topic_map[client_id]
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

class Connection(object):
    """A client connection to a channel."""

    def __init__(self, flex_client_id, channel):
        self.flex_client_id = flex_client_id # Unique for each Flex client.
        self.channel = channel
        
        self._last_active = int(time.time())
        self._messages = []
        self._subscriptions = {}

    def getSubscriptions(self):
        lock = threading.RLock()
        lock.acquire()
        try:
            subscriptions = self._subscriptions.values()
        finally:
            lock.release()

        return subscriptions

    def subscribe(self, client_id, topic):
        subscription = Subscription(self, client_id, topic)

        lock = threading.RLock()
        lock.acquire()
        try:
            client_subscriptions = self._subscriptions.get(client_id, None)
            if client_subscriptions is None:
                client_subscriptions = {}
                self._subscriptions[client_id] = client_subscriptions
            client_subscriptions[topic] = subscription
        finally:
            lock.release()

        return subscription

    def unsubscribe(self, client_id, topic):
        lock = threading.RLock()
        lock.acquire()
        try:
            client_subscriptions = self._subscriptions.get(client_id, None)
            if client_subscriptions is not None:
                if topic in client_subscriptions:
                    del client_subscriptions[topic]
        finally:
            lock.release()

    def poll(self):
        """Returns all current messages and empties que."""
        lock = threading.RLock()
        lock.acquire()
        try:
             results = self._messages
             self._messages = []
             self._last_active = int(time.time())
        finally:
            lock.release()

        return results

    def publish(self, msg):
        lock = threading.RLock()
        lock.acquire()
        try:
            self._messages.append(msg)
        finally:
            lock.release()

    def clean(self, current_time=None):
        """Remove all expired messages."""
        if current_time is None:
            current_time = int(time.time())

        tmp = []
        lock = threading.RLock()
        lock.acquire()
        try:
             for msg in self._messages:
                 if msg.isExpired(current_time):
                     continue
                 tmp.append(msg)
             self._messages = tmp
        finally:
            lock.release()

class Channel(object):
    """An individual channel that can be send/recieve messages."""

    def __init__(self, name, max_connections=-1, connection_class=Connection):
        self.name = name
        self.max_connections = max_connections
        self.connection_class = connection_class
        
        self._connections = {}
        self._channel_set = None

    def getConnection(self, flex_client_id):
        lock = threading.RLock()
        lock.acquire()
        try:
            connection = self._connections.get(flex_client_id, None)
        finally:
            lock.release()

        return connection

    def connect(self, flex_client_id):
        """Add a client connection to this channel.

        Returns Connection
        """
        if self.max_connections > -1 and len(self._connections) >= self.max_connections:
            raise ChannelError("Channel '%s' is not accepting connections." % self.name)

        connection = self.connection_class(flex_client_id, self)
       
        lock = threading.RLock() 
        lock.acquire()
        try:
            self._connections[flex_client_id] = connection
        finally:
            lock.release()

        return connection

    def disconnect(self, flex_client_id):
        """Remove a client connection from this channel."""
        lock = threading.RLock()
        lock.acquire()
        try:
            if flex_client_id in self._connections:
               # Delete any subscriptions
               connection = self._connections[flex_client_id]
               subscriptions = connection.getSubscriptions()
               msg_agent = self._channel_set.message_agent
               for subscription in subscriptions:
                   msg_agent.unsubscribe(subscription.connection,
                       subscription.client_id, subscription.topic)
                   
               del self._connections[flex_client_id]
        finally:
            lock.release()

    def clean(self):
        pass

class AmfChannel(Channel):
    """An individual channel that can be send/recieve AMF packets."""

    def __init__(self, name, max_connections=-1,
        connection_class=Connection, encoder=None, decoder=None):
        Channel.__init__(self, name, max_connections, connection_class)

        if encoder is None:
            encoder = Encoder()
        self.encoder = encoder

        if decoder is None:
            decoder = Decoder()
        self.decoder = decoder

    def invoke(self, raw_packet):
        """Invoke an incoming request packet."""
        if amfast.log_debug:
            amfast.logger.debug("<channel name=\"%s\">Processing incoming packet.</channel>" % self.name)

        request = None
        try:
            request = self.decodePacket(raw_packet)
            request.channel_set = self._channel_set
            return self.encodePacket(request.invoke())
        except AmFastError, exc:
            amfast.log_exc()

            if request is not None:
               return self.encodePacket(request.fail(exc))
            else:
                # There isn't much we can do if
                # the request was not decoded correctly.
                raise

    def decodePacket(self, raw_packet):
        if amfast.log_debug:
            if hasattr(raw_packet, "upper"):
                # Only print this if raw_packet is a string
                amfast.logger.debug("<rawRequestPacket>%s</rawRequestPacket>" %
                    amfast.format_byte_string(raw_packet))

        return self.decoder.decode_packet(raw_packet)

    def encodePacket(self, packet):
        raw_packet = self.encoder.encode_packet(packet)

        if amfast.log_debug:
            if hasattr(raw_packet, "upper"):
                # Only print this if raw_packet is a string
                amfast.logger.debug("<rawResponsePacket>%s</rawResponsePacket>" %
                    amfast.format_byte_string(raw_packet))

        return raw_packet

class ChannelSet(object):
    """A client can access the same RPC exposed methods
    from any of the channels in the ChannelSet.
    """

    def __init__(self, service_mapper=None, message_agent=None):
        if service_mapper is None:
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        if message_agent is None:
            message_agent = MessageAgent()
        self.message_agent = message_agent

        self._channels = {}

    def __iter__(self):
        return self._channels.itervalues()

    def mapChannel(self, channel):
        lock = threading.RLock()
        lock.acquire()
        try:
            self._channels[channel.name] = channel
            channel._channel_set = self
        finally:
            lock.release()

    def unMapChannel(self, channel):
        lock = threading.RLock()
        lock.acquire()
        try:
            if channel.name in self._channels:
                channel._channel_set = None
                del self._channels[channel.name]
        finally:
            lock.release()

    def getChannel(self, name):
        lock = threading.RLock()
        lock.acquire()
        try:
            channel = self._channels[name]
        finally:
            lock.release()
        return channel

    def getConnection(self, flex_client_id):
        for channel in self._channels.values():
            connection = channel.getConnection(flex_client_id)
            if connection is not None:
                return connection
        return None

    def clean(self):
        pass
