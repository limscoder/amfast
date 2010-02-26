"""Endpoints specify how messages are encoded and decoded."""

import amfast

class Endpoint(object):
    def logRaw(self, label, raw):
        if hasattr(raw, "upper"):
            amfast.logger.debug("<%s>%s</%s>" %
                    (label, repr(raw), label))

class AmfEndpoint(Endpoint):
    """An Endpoint that can encode/decode AMF packets.

    arguments
    ==========
     * encoder - amfast.encoder.Encoder, object used to encode AMF Packets.
     * decoder - amfast.decoder.Decoder, object used to decode AMF Packets.
    """

    def __init__(self, encoder=None, decoder=None):
        if encoder is None:
            from amfast.encoder import Encoder
            encoder = Encoder()
        self.encoder = encoder

        if decoder is None:
            from amfast.decoder import Decoder
            decoder = Decoder()
        self.decoder = decoder

    def decodePacket(self, raw_packet, *args, **kwargs):
        """Decode an AMF packet."""
        if amfast.log_raw:
            self.logRaw('rawDecodePacket', raw_packet)

        return self.decoder.decode_packet(raw_packet)

    def encodePacket(self, packet):
        """Encode an AMF packet."""
        raw_packet = self.encoder.encode_packet(packet)

        if amfast.log_raw:
            self.logRaw('rawEncodePacket', raw_packet)

        return raw_packet

    def decode(self, raw_obj, amf3=None):
        """Decode an AMF object."""
        if amfast.log_raw:
            self.logRaw('rawDecodeObject', raw_obj)

        return self.decoder.decode(raw_obj, amf3)

    def encode(self, obj, amf3=None):
        """Encode an AMF object."""
        raw_obj = self.encoder.encode(obj, amf3)

        if amfast.log_raw:
            self.logRaw('rawEncodeObject', raw_obj)

        return raw_obj
