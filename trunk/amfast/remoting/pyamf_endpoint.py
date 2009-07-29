"""Use PyAmf for encoding and decoding."""

import logging

import pyamf
from pyamf import util as pyamf_util
import pyamf.remoting

import amfast
from endpoint import Endpoint
import pyamf_converter as pc

class PyAmfEndpoint(Endpoint):
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
        if amfast.log_raw:
            self.logRaw('rawDecodePacket', raw_packet)

        context = pyamf.get_context(pyamf.AMF0)
        pyamf_packet = pyamf.remoting.decode(raw_packet, context)
        packet = pc.packet_to_amfast(pyamf_packet)

        if amfast.log_debug:
            amfast.logger.debug("<decodedPyAmfPacket>%s</decodedPyAmfPacket>" % pyamf_packet)

        return packet

    def encodePacket(self, packet):
        pyamf_packet = pc.packet_to_pyamf(packet)
        if amfast.log_debug:
            amfast.logger.debug("<encodedPyAmfPacket>%s</encodedPyAmfPacket>" % pyamf_packet)

        context = pyamf.get_context(pyamf.AMF0)
        stream = pyamf.remoting.encode(pyamf_packet, context)
        raw_packet = stream.getvalue()

        if amfast.log_raw:
            self.logRaw('rawEncodePacket', raw_packet)

        return raw_packet

    def decode(self, raw_obj, amf3=False):
        if amf3 is True:
            amf_type = pyamf.AMF3
        else:
            amf_type = pyamf.AMF0

        context = pyamf.get_context(amf_type)
        decoder = pyamf.get_decoder(amf_type, raw_obj, context=context)
        obj = decoder.readElement()

        if amfast.log_raw:
            self.logRaw('rawDecodeObject', raw_obj)

        return obj

    def encode(self, obj, amf3=False):
        if amf3 is True:
            amf_type = pyamf.AMF3
        else:
            amf_type = pyamf.AMF0

        stream = pyamf_util.BufferedByteStream()

        context = pyamf.get_context(amf_type)
        encoder = pyamf.get_encoder(amf_type, stream, context=context)
        encoder.writeElement(obj)

        raw_obj = stream.getvalue()

        if amfast.log_raw:
            self.logRaw('rawEncodeObject', raw_obj)

        return raw_obj
