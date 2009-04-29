"""Use PyAmf for encoding and decoding"""

import logging

import pyamf
import pyamf.remoting

import amfast
import pyamf_converter as pc

class PyAmfEndpoint(object):
    """An Endpoint that can encode/decode AMF packets with PyAmf.

    !!!YOU MUST MAP CLASS DEFINITIONS WITH PyAMF!!!
    """

    def decodePacket(self, raw_packet, *args, **kwargs):
        context = pyamf.get_context(pyamf.AMF0)
        pyamf_packet = pyamf.remoting.decode(raw_packet, context)
        packet = pc.packet_to_amfast(pyamf_packet)

        if amfast.log_debug:
            if hasattr(raw_packet, "upper"):
                # Only print this if raw_packet is a string
                amfast.logger.debug("<rawRequestPacket>%s</rawRequestPacket>" %
                    amfast.format_byte_string(raw_packet))
            amfast.logger.debug("<DecodedPyAmfPacket>%s</DecodedPyAmfPacket>" % pyamf_packet)

        return packet

    def encodePacket(self, packet):
        context = pyamf.get_context(pyamf.AMF0)
        pyamf_packet = pc.packet_to_pyamf(packet)
        stream = pyamf.remoting.encode(pyamf_packet, context)
        raw_packet = stream.getvalue()

        if amfast.log_debug:
            amfast.logger.debug("<EncodedPyAmfPacket>%s</EncodedPyAmfPacket" % pyamf_packet)
            if hasattr(raw_packet, "upper"):
                amfast.logger.debug("<rawResponsePacket>%s</rawResponsePacket>" %
                    amfast.format_byte_string(raw_packet))

        return raw_packet
