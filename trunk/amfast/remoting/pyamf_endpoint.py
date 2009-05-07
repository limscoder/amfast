"""Use PyAmf for encoding and decoding"""

import logging

import pyamf
import pyamf.remoting

import amfast
import pyamf_converter as pc

class PyAmfEndpoint(object):
    """An Endpoint that can encode/decode AMF packets with PyAmf.

    How to configure custom class mapping:

# When using the PyAmfEndpoint,
# custom type mapping can be configured
# either through AmFast, or through PyAmf.

# Configure type mapping with AmFast
class_mapper = ClassDefMapper()

#... map classes ...#

# Use pyamf_converter to automatically map classes
# from a ClassDefMapper with PyAmf.
import amfast.remoting.pyamf_converter as pyamf_converter
pyamf_converter.register_class_mapper(class_mapper)

# Configure type mapping directly with PyAmf.
# Use the standard PyAmf way of mapping classes.
pyamf.register_class(klass, 'alias', ....)
    """

    def decodePacket(self, raw_packet, *args, **kwargs):
        context = pyamf.get_context(pyamf.AMF0)
        pyamf_packet = pyamf.remoting.decode(raw_packet, context)
        packet = pc.packet_to_amfast(pyamf_packet)

        if amfast.log_raw:
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

        if amfast.log_raw:
            amfast.logger.debug("<EncodedPyAmfPacket>%s</EncodedPyAmfPacket" % pyamf_packet)
            if hasattr(raw_packet, "upper"):
                amfast.logger.debug("<rawResponsePacket>%s</rawResponsePacket>" %
                    amfast.format_byte_string(raw_packet))

        return raw_packet
