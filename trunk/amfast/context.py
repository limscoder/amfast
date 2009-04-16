"""Contexts keep track of state during encoding and decoding."""

from cStringIO import StringIO

from class_def import ClassDefMapper

class ObjectContext(object):
    """Maps objects to indexes."""

    def __init__(self):
        self.idx = 0;
        self._map = {}

    def mapObject(self, obj):
        self._map[id(obj)] = idx
        idx += 1

    def getIndex(self, obj):
        return self._map.get(id(obj), None)

class IdxContext(object):
    """Maps indexes to objects."""

    def __init__(self):
        self._map = []

    def mapObject(self, obj):
        self._map.append(obj)

    def getObject(self, idx):
        return self._map[idx]

class EncoderContext(object):
    """Holds information relevant to a single run through the encoder."""

    def __init__(self, file_obj=None):
        if file_obj is None:
            # Create new buffer
            file_obj = StringIO()
        self.file_obj = file_obj
        self.object_context = ObjectContext()

    def copy(self):
        return self.__class__(self.file_obj)
       
class Amf3EncoderContext(object):
    """Holds information relevant to a single AMF3 run."""

    def __init__(self, file_obj=None):
        EncoderContext.__init__(self, file_obj)
        self.string_context = ObjectContext()
        self.class_context = ObjectContext()

    def copy(self):
        copy = EncoderContext.copy(self)
        copy.string_context = ObjectContext()
        copy.class_context = ObjectContext()
        return copy

class DecoderContext(object):
    """
    Holds information relevant to a single run through the decoder.

    attributes
    ===========
     * file_obj - file-like-object, input stream.
     * class_def_mapper - amfast.class_def.ClassDefMapper,
         determines how objects are decoded.
     * amf3 - bool, True if input stream is AMF3 format.
    """

    def __init__(self, file_obj, class_def_mapper=None, amf3=False):
        """
        arguments
        ==========
         * file_object - string or file like object.
         * class_def_mapper - amfast.class_def.ClassDefMapper,
             Default == None (all objects are anonymous)
         * amf3 - bool, Default == False.
         """

        if hasattr(file_obj, 'upper'):
            # Create new buffer with string
            file_obj = StringIO(file_obj)
        self.file_obj = file_obj

        if class_def_mapper is None:
            class_def_mapper = ClassDefMapper()
        self.class_def_mapper = class_def_mapper

        self.amf3 = amf3

        # Create contexts
        self.object_context = IdxContext()

        if self.amf3 is True:
            self.string_context = IdxContext()
            self.class_context = IdxContext()

    def copy(self, file_obj=None, amf3=None):
        """Resets object contexts, but uses the original file object."""
        if file_obj is None:
            file_obj = self.file_obj

        if amf3 is None:
            amf3 = self.amf3

        return self.__class__(file_obj, self.class_def_mapper, amf3=amf3)
