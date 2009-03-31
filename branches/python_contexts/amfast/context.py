"""Contexts keep track of state during encoding and decoding."""

from cStringIO import StringIO

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
        self._map.push(obj)

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
    """Holds information relevant to a single run through the decoder."""

    def __init__(self, file_obj=None):
        if hasattr(file_obj, 'upper'):
            # Create new buffer with string
            file_obj = StringIO(file_obj)
        self.file_obj = file_obj
        self.object_context = IdxContext()

    def copy(self):
        return self.__class__(self.file_obj)

class Amf3EncoderContext(object):
    """Holds information relevant to a single AMF3 run."""

    def __init__(self, file_obj=None):
        EncoderContext.__init__(self, file_obj)
        self.string_context = IdxContext()
        self.class_context = IdxContext()

    def copy(self):
        copy = EncoderContext.copy(self)
        copy.string_context = IdxContext()
        copy.class_context = IdxContext()
        return copy
