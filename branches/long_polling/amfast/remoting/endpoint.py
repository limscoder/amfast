"""Endpoints specify how messages are encoded and decoded."""

import amfast
from amfast.encoder import Encoder
from amfast.decoder import Decoder

class AmfEndpoint(object):
    """An Endpoint that can encode/decode AMF packets.

    arguments
    ==========
     * encoder - amfast.encoder.Encoder, object used to encode AMF Packets.
     * decoder - amfast.decoder.Decoder, object used to decode AMF Packets.
    """

    def __init__(self, encoder=None, decoder=None):
        if encoder is None:
            encoder = Encoder()
        self.encoder = encoder

        if decoder is None:
            decoder = Decoder()
        self.decoder = decoder

    def decodePacket(self, raw_packet, *args, **kwargs):
        if amfast.log_raw:
            if hasattr(raw_packet, "upper"):
                # Only print this if raw_packet is a string
                amfast.logger.debug("<rawRequestPacket>%s</rawRequestPacket>" %
                    amfast.format_byte_string(raw_packet))

        return self.decoder.decode_packet(raw_packet)

    def encodePacket(self, packet):
        raw_packet = self.encoder.encode_packet(packet)

        if amfast.log_raw:
            if hasattr(raw_packet, "upper"):
                # Only print this if raw_packet is a string
                amfast.logger.debug("<rawResponsePacket>%s</rawResponsePacket>" %
                    amfast.format_byte_string(raw_packet))

        return raw_packet
