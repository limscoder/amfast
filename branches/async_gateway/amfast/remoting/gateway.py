"""Send and receive AMF messages."""

import uuid

import threading

import amfast
from amfast import decoder, encoder
from amfast.class_def import ClassDefMapper
from amfast.remoting import ServiceMapper

class Channel(object):
    def __init__(self, name):
        self.name = name

    def invoke(self, package, message):
        return message.invoke(package)

class Gateway(object):
    """An AMF messaging gateway can send and receive AMF packets."""

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

        self._lock = threading.RLock()
        self._channels = {}
        self._mapBuiltIns()

    def _mapBuiltIns(self):
        """Map built-in channels."""
        self.mapChannel(Channel('amf'))
        # TODO: REMOVE THIS (for testing only)
        self.mapChannel(Channel('amfast-channel'))

    def processPacket(self, raw_packet):
        """Process an incoming packet."""
        if amfast.log_debug:
            amfast.logger.debug("<gateway>Processing incoming packet.</gateway>")

        request = None
        try:
            request = self.decodePacket(raw_packet)
            request.gateway = self
            return self.encodePacket(request.invoke())
        except Exception, exc:
            amfast.log_exc()

            if request is not None:
               return self.encodePacket(request.fail(exc))
            else:
                # There isn't much we can do if
                # the request was not decoded correctly.
                raise exc

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
        """Maps a channel

        arguments
        ==========
         * channel - remoting.channel.Channel, the channel to set.
        """
        self._lock.acquire()
        try:
            self._channels[channel.name] = channel
        finally:
            self._lock.release()

    def unMapChannel(self, channel):
        """Un-maps a channel

        arguments
        ==========
         * channel - Channel, the channel to un-map.
        """
        self._lock.acquire()
        try:
            if channel.name in self._channels:
                del self._channels[channel.name]
        finally:
            self._lock.release()

    def getChannelByName(self, name):
        """Get a channel by name.

        arguments
        ==========
         * name - string, channel name.
        """
        return self._channels.get(name, None)
