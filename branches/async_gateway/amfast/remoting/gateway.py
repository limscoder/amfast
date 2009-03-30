"""Send and receive AMF messages."""

import uuid

import threading

import amfast
from amfast import decoder, encoder
from amfast.class_def import ClassDefMapper
from amfast.remoting import ServiceMapper, RemotingError

class GatewayError(RemotingError):
    pass

class Channel(object):
    """An individual channel that AMF packets can be sent/recieved from/to."""

    def __init__(self, name, gateway, max_connections=-1):
        self.name = name
        self.gateway = gateway
        self.max_connections = max_connections

    def _getGateway(self):
        return self._gateway

    def _setGateway(self, gateway):
        self._gateway = gateway
        self._gateway.message_publisher.mapChannel(channel)
    gateway = property(_getGateway, _setGateway)

    def isAcceptingSubscriptions(self):
        return True
        #if self.max_connections > -1:
        #    if self.connections >= self.max_connections:
        #        return False
        #return True

    def invoke(self, raw_packet):
        """Invokes a remoting message."""
        return self._gateway.invoke(raw_packet)

class Subscription(object):
    """A client subscription to a channel."""
    def __init__(self, topic, client_id):
        self.topic = topic
        self.client_id = client_id
        self.last_active = now()
        self._messages = []

class MessagePublisher(object):
    """Publishes messages."""
    def __init__(self):
        self._lock = threading.RLock()
        self._channels = {}
        self._subscriptions = {}

    def subscribe(self, topic, client_id):
        self._lock.acquire()
        try:
            topic_map = self._subscriptions.get(topic, None)
            if topic is None:
                topic_map = {}
                self._subscriptions[topic] = topic_map

            topic_map[client_id] = Subscription(topic, client_id)
        finally:
            self._lock.release()

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

class Gateway(object):
    """An AMF messaging gateway can encode and decode AMF packets."""

    def __init__(self, service_mapper=None, class_def_mapper=None,
        use_array_collections=False, use_object_proxies=False,
        use_references=True, use_legacy_xml=False, include_private=False):

        self.service_mapper = service_mapper
        if self.service_mapper is None:
            self.service_mapper = ServiceMapper()

        self.class_def_mapper = class_def_mapper
        if self.class_def_mapper is None:
            self.class_def_mapper = ClassDefMapper()

        self.use_array_collections = use_array_collections
        self.use_object_proxies = use_object_proxies
        self.use_references = use_references
        self.use_legacy_xml = use_legacy_xml
        self.include_private = include_private
        self.gateway_id = str(uuid.uuid4())
       
        # 'public' access should be read-only
        # don't want to mess this up.
        self._message_publisher = MessagePublisher()

    def _getMessagePublisher(self):
        return self._message_publisher
    message_publisher = property(_getMessagePublisher) 

    def invoke(self, raw_packet):
        """Invoke an incoming request packet."""
        if amfast.log_debug:
            amfast.logger.debug("<gateway>Processing incoming packet.</gateway>")

        request = None
        try:
            request = self.decodePacket(raw_packet)
            request.gateway = self
            return self.encodePacket(request.invoke())
        except AmFastException, exc:
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
