from amfast.decode import decode, decode_packet
from amfast.context import DecoderContext
from amfast.class_def import ClassDefMapper

class Decoder(object):
    """A wrapper class for convenient access to amfast.decode.decode.

    Decoder
    ========
     * amf3 - bool - True to decode as AMF3.
     * class_def_mapper - amfast.class_def.ClassDefMapper - The object that retrieves ClassDef objects.
    """ 

    def __init__(self, amf3=False, class_def_mapper=None):

        self.amf3 = amf3

        if class_def_mapper is None:
            class_def_mapper = ClassDefMapper()
        self.class_def_mapper = class_def_mapper

    def _getContext(self, input, amf3=None):
        if amf3 is None:
            amf3 = self.amf3
        return DecoderContext(input, amf3=amf3, class_def_mapper=self.class_def_mapper)

    def decode(self, val, amf3=None):
        """Decode a string or file-like-object from AMF."""
        return decode(self._getContext(val, amf3))

    def decode_packet(self, val, amf3=None):
        """Decode a string or file-like-object representing an AMF packet."""
        return decode_packet(self._getContext(val, amf3))
