from amfast.encode import encode, encode_packet
from amfast.context import EncoderContext
from amfast.class_def import ClassDefMapper

class Encoder(object):
    """A wrapper class for convenient access to amfast.encode.encode.

    Encoder
    ========
     * amf3 - bool - True to encode as AMF3.
     * use_collections - bool - True to encode lists and tuples as ArrayCollections.
     * use_proxies - bool - True to encode dicts as ObjectProxies.
     * use_references - bool - True to encode multiply occuring objects by reference.
     * use_legacy_xml - bool - True to XML as XMLDocument instead of e4x.
     * include_private - bool - True to encode attributes starting with '_'.
     * class_def_mapper - amfast.class_def.ClassDefMapper - The object that retrieves ClassDef objects.
     * buffer - file-like-object - Output buffer. Set to None to output to a string.

    """ 

    def __init__(self, amf3=False, use_collections=False, use_proxies=False,
        use_references=True, use_legacy_xml=False, include_private=False,
        class_def_mapper=None, buffer=None):

        self.amf3 = amf3
        self.use_collections = use_collections
        self.use_proxies = use_proxies
        self.use_references = use_references
        self.use_legacy_xml = use_legacy_xml
        self.include_private = include_private

        if class_def_mapper is None:
            class_def_mapper = ClassDefMapper()
        self.class_def_mapper = class_def_mapper

        self.buffer = buffer

    def _getContext(self, amf3=None):
        if amf3 is None:
            amf3 = self.amf3

        kwargs = {
            'amf3': amf3,
            'use_collections': self.use_collections,
            'use_proxies': self.use_proxies,
            'use_references': self.use_references,
            'use_legacy_xml': self.use_legacy_xml,
            'include_private': self.include_private,
            'class_def_mapper': self.class_def_mapper
        }
 
        if self.buffer is not None:
            kwargs['buffer'] = self.buffer

        return EncoderContext(**kwargs);

    def encode(self, val, amf3=None):
        """Encode a value to AMF."""
        return encode(val, self._getContext(amf3))

    def encode_packet(self, val, amf3=None):
        """Encode an AMF packet."""
        return encode_packet(val, self._getContext(amf3))
