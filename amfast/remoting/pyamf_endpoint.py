"""Use PyAmf for encoding and decoding"""

import pyamf
import pyamf.remoting

import pyamf_converter as pc

class PyAmfEndpoint(object):
    """An Endpoint that can encode/decode AMF packets with PyAmf.

    YOU MUST MAP CLASS DEFINITIONS WITH PyAMF
    """

    def decodePacket(self, raw_packet, *args, **kwargs):
        context = pyamf.get_context(pyamf.AMF0)
        pyamf_packet = pyamf.remoting.decode(raw_packet, context)
        return pc.packet_to_amfast(pyamf_packet)

    def encodePacket(self, packet):
        context = pyamf.get_context(pyamf.AMF0)
        pyamf_packet = pc.packet_to_pyamf(packet)
        stream = pyamf.remoting.encode(pyamf_packet, context)
        return stream.getValue()
