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

class ChannelError(RemotingError):
    pass

class MessageBroker(object):
    """Publishes messages."""

    SUBTOPIC_SEPARATOR = "_;_"

    def __init__(self):
        self._lock = threading.RLock()
        self._topics = {} # Messages will be published by topic
        self._clients = {} # Messages will be retrieved by client

    def subscribe(self, client_id, channel, topic,
        sub_topic=None, selector=None):
        """Subscribe a client to a topic and channel."""

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        self._lock.acquire()
        try:
            subscription = self._clients.get(client_id, None)
            if subscription is None:
                subscription = channel.connect(client_id)
                self._clients[client_id] = subscription

            topic_map = self._topics.get(topic, None)
            if topic_map is None:
                topic_map = {}
                self._topics[topic] = topic_map

            topic_map[client_id] = subscription
        finally:
            self._lock.release()

    def disconnect(self, client_id):
        """Disconnect a client from a topic and channel."""

        self._lock.acquire()
        try:
            if client_id in self._clients:
                self._clients[client_id].channel.disconnect(client_id)
                del self._clients[client_id]

            del_topics = [] # Empty topics to delete
            for topic, topic_map in self._topics.iteritems():
                if client_id in topic_map:
                    del topic_map[client_id]

                if len(topic_map) == 0:
                    del_topics.append(topic)

            for topic in del_topics:
                del self._topics[topic]
        finally:
            self._lock.release

    def poll(self, client_id):
        self._lock.acquire()
        try:
             if client_id not in self._clients:
                 raise ChannelError("Client is not subscribed.")
             return self._clients[client_id].poll()
        finally:
            self._lock.release

    def clean(self, timeout, current_time=None):
        if current_time is None:
            current_time = time.time()

        for client_id, subscription in self._clients.iteritems():
            if (current_time - subscription.last_active) > timeout:
                self.disconnect(client_id)
            else:
                subscription.clean(current_time)

class Subscription(object):
    """A client subscription over a channel."""

    def __init__(self, client_id, channel):
        self.client_id = client_id
        self.channel = channel
        
        self.last_active = time.time()

        self._lock = threading.RLock()
        self._messages = []

    def poll(self):
        """Returns all current messages and empties que."""
        self._lock.acquire()
        try:
             results = self._messages
             self._messages = []
             self.last_active = time.time()
        finally:
            self._lock.release()

        return results

    def clean(self, current_time=None):
        """Remove all expired messages."""
        if current_time is None:
            current_time = time.time()

        tmp = []
        self._lock.acquire()
        try:
             for msg in self._messages:
                 if msg.isExpired(current_time):
                     continue
                 tmp.append(msg)
             self._messages = tmp
        finally:
            self._lock.release()

class Channel(object):
    """An individual channel that AMF packets can be sent/recieved from/to."""

    def __init__(self, name, encoder=None, decoder=None, max_subscriptions=-1):
        self.name = name
        self.max_subscriptions = max_subscriptions
        self.current_subscriptions = 0

        if encoder is None:
            encoder = Encoder()
        self.encoder = encoder

        if decoder is None:
            decoder = Decoder()
        self.decoder = decoder

        self._lock = threading.RLock()
        self._channel_set = None

    def connect(self, client_id):
        """Add a client subscription to this channel.

        Returns Subscription
        """
        subscription = Subscription(client_id, self)
        
        self._lock.acquire()
        try:
            if self.max_subscriptions > -1:
                # Check for maximum number of subscriptions
                if self.current_subscriptions >= self.max_subscriptions:
                    raise ChannelError("Channel '%s' is not accepting subscriptions." % self.name)
            self.current_subscriptions += 1
        finally:
            self._lock.release()

        return subscription

    def disconnect(self, client_id):
        """Remove a client connection from this channel."""
        self._lock.acquire()
        try:
            self.current_subscriptions -= 1
        finally:
            self._lock.release()

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

    def __init__(self, service_mapper=None, message_broker=None):
        if service_mapper is None:
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        if message_broker is None:
            message_broker = MessageBroker()
        self.message_broker = message_broker

        self._lock = threading.RLock()
        self._channels = {}

    def __iter__(self):
        return self._channels.itervalues()

    def mapChannel(self, channel):
        self._lock.acquire()
        try:
            self._channels[channel.name] = channel
            channel._channel_set = self
        finally:
            self._lock.release()

    def unMapChannel(self, channel):
        self._lock.acquire()
        try:
            if channel.name in self._channels:
                channel._channel_set = None
                del self._channels[channel.name]
        finally:
            self._lock.release()

    def getChannel(self, name):
        self._lock.acquire()
        try:
            channel = self._channels[name]
        finally:
            self._lock.release()
        return channel
