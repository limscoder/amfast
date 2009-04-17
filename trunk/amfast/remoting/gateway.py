"""Send and receive AMF messages."""

import uuid

import threading

import amfast
from amfast import AmFastError, decoder, encoder
from amfast.class_def import ClassDefMapper
from amfast.remoting import ServiceMapper, RemotingError

class GatewayError(RemotingError):
    pass

class Subscription(object):
    """A client subscription to a topic over a channel."""

    def __init__(self, client_id, channel, topic, selector=None):
        self.client_id = client_id
        self.channel = channel
        self.topic = topic
        self.selector = selector
        
        #self.last_active = now()

        #self._lock = threading.RLock()
        #self._messages = []

class Channel(object):
    """An individual channel that AMF packets can be sent/recieved from/to."""

    def __init__(self, name, gateway, max_subscriptions=-1):
        self.name = name
        self.gateway = gateway
        self.max_subscriptions = max_subscriptions
        self.current_subscriptions = 0

        self._lock = threading.RLock()

    def _getGateway(self):
        return self._gateway

    def _setGateway(self, gateway):
        self._gateway = gateway
        self._gateway.mapChannel(self)
    gateway = property(_getGateway, _setGateway)

    def subscribe(self, client_id, topic, selector=None):
        """Add a client subscription to this channel.

        Returns Subscription
        """
        subscription = Subscription(client_id, self, topic, selector)
        
        self._lock.acquire()
        try:
            if self.max_subscriptions > -1:
                # Check for maximum number of subscriptions
                if self.current_subscriptions >= self.max_subscriptions:
                    raise GatewayException("Channel '%s' is not accepting subscriptions." % self.name)
            self.current_subscriptions += 1
        finally:
            self._lock.release()

        return subscription

    def invoke(self, raw_packet):
        """Invokes a remoting message."""
        return self.gateway.invoke(raw_packet)

class MessagePublisher(object):
    """Publishes messages."""

    SUBTOPIC_SEPARATOR = "_;_"

    def __init__(self):
        self._lock = threading.RLock()
        self._subscriptions = {}

    def subscribe(self, client_id, channel, topic,
        sub_topic=None, selector=None):
        """Subscribe a client to a topic and channel."""

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        self._lock.acquire()
        try:
            topic_map = self._subscriptions.get(topic, None)
            if topic_map is None:
                topic_map = {}
                self._subscriptions[topic] = topic_map

            topic_map[client_id] = channel.subscribe(client_id, topic, selector)
        finally:
            self._lock.release()

class Gateway(object):
    """An AMF messaging gateway can encode and decode AMF packets."""

    def __init__(self, service_mapper=None, class_def_mapper=None,
        message_publisher=None, use_array_collections=False,
        use_object_proxies=False, use_references=True, use_legacy_xml=False,
        include_private=False):

        self.service_mapper = service_mapper
        if self.service_mapper is None:
            self.service_mapper = ServiceMapper()

        self.class_def_mapper = class_def_mapper
        if self.class_def_mapper is None:
            self.class_def_mapper = ClassDefMapper()

        self.message_publisher = message_publisher
        if self.message_publisher is None:
            self.message_publisher = MessagePublisher()

        self.use_array_collections = use_array_collections
        self.use_object_proxies = use_object_proxies
        self.use_references = use_references
        self.use_legacy_xml = use_legacy_xml
        self.include_private = include_private
        self.gateway_id = str(uuid.uuid4())

        self._lock = threading.RLock()
        self._channels = {}
       
    def invoke(self, raw_packet):
        """Invoke an incoming request packet."""
        if amfast.log_debug:
            amfast.logger.debug("<gateway>Processing incoming packet.</gateway>")

        request = None
        try:
            request = self.decodePacket(raw_packet)
            request.gateway = self
            return self.encodePacket(request.invoke())
        except AmFastError, exc:
            amfast.log_exc()

            if request is not None:
               return self.encodePacket(request.fail(exc))
            else:
                # There isn't much we can do if
                # the request was not decoded correctly.
                raise
        except Exception:
            amfast.log_exc()
            raise

    def decodePacket(self, raw_packet):
        if amfast.log_debug:
            amfast.logger.debug("<rawRequestPacket>%s</rawRequestPacket>" %
                amfast.format_byte_string(raw_packet))

        return decoder.decode(raw_packet, packet=True,
            class_def_mapper=self.class_def_mapper)

    def encodePacket(self, packet):
        raw_packet = encoder.encode(packet, packet=True,
            class_def_mapper=self.class_def_mapper,
            use_array_collections=self.use_array_collections,
            use_object_proxies=self.use_object_proxies,
            use_references=self.use_references, use_legacy_xml=self.use_legacy_xml,
            include_private=self.include_private, amf3=packet.is_amf3)

        if amfast.log_debug:
            amfast.logger.debug("<rawResponsePacket>%s</rawResponsePacket>" %
                amfast.format_byte_string(raw_packet))

        return raw_packet

    def mapChannel(self, channel):
        self._lock.acquire()
        try:
            self._channels[channel.name] = channel
        finally:
            self._lock.release()

    def unMapChannel(self, channel):
        self._lock.acquire()
        try:
            if channel.name in self._channels:
                del self._channels[channel.name]
        finally:
            self._lock.release()

    def getChannelByName(self, name):
        self._lock.acquire()
        try:
            channel = self._channels[name]
        finally:
            self._lock.release()
        return channel
