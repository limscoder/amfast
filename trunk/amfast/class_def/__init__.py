"""Provides an interface for determining how Python objects are serialized and de-serialized."""

from amfast import AmFastError

class ClassDefError(AmFastError):
    """ClassDef related errors."""
    pass

class ClassDef(object):
    """Defines how objects of a given class are serialized and de-serialized.
    This class can be sub-classed to provide custom serialization.

    attributes
    ===========
     * class_ - class, the class object mapped to this definition
     * alias - string, the amf alias name of the mapped class
     * static_attrs - tuple, a tuple of static attribute names, all values must be strings or unicode
    """

    CLASS_DEF = True

    def __init__(self, class_, alias, static_attrs):
        """arguments
        =========
         * class_ - class, the class being mapped.
         * alias - string, specifies the amf class alias.
         * static_attrs - tuple, a tuple of static attribute strings.
        """
        self.class_ = class_
        self.alias = alias
        self.static_attrs = static_attrs
        self._decoded_attrs = None # This value gets set by the decoder, don't mess with it.

    def getStaticAttrVals(self, obj):
        """Returns a list of values of attributes defined in self.static_attrs

        If this method is overridden to provide custom behavior, please note:
        Returned values MUST BE IN THE SAME ORDER AS THEY APPEAR IN self.static_attrs.

        arguments
        ==========
         * obj - object, the object to get attribute values from.
        """
        vals = []
        for attr in self.static_attrs:
            vals.append(getattr(obj, attr, None))
        return vals

    def getInstance(self):
        """Returns an instance of the mapped class to be used 
        when an object of this type is deserialized.
        """
        return self.class_.__new__(self.class_)

    def applyAttrVals(self, obj, vals):
        """Set decoded attribute values on the object.

        arguments
        ==========
         * obj - object, the object to set the attribute values on.
         * vals - dict, keys == attribute name, values == attribute values.
        """
        for key, val in vals.iteritems():
            setattr(obj, key, val)

class DynamicClassDef(ClassDef):
    """A ClassDef with dynamic attributes."""

    DYNAMIC_CLASS_DEF = True

    def __init__(self, class_, alias, static_attrs):
        ClassDef.__init__(self, class_, alias, static_attrs)

    def getDynamicAttrVals(self, obj, include_private=False):
        """Returns a dict where keys are attribute names and values are attribute values.

        arguments
        ==========
        obj - object, the object to get attributes for.
        include_private - bool, if False do not include attributes with
            names starting with '_'. Default = False.
        """
        return get_dynamic_attr_vals(obj, self.static_attrs, include_private=False);

class ExternizeableClassDef(ClassDef):
    """A ClassDef where the byte string encoding/decoding is customized."""
    
    EXTERNIZEABLE_CLASS_DEF = True
    
    def __init__(self, class_, alias, static_attrs):
        ClassDef.__init__(self, class_, alias, static_attrs)
 
    def writeByteString(self, obj):
        """Returns a byte string representation of the object.

        This method must be overridden in a sub-class.

        The return value can be a string or a ByteArray.
        """

        raise ClassDefError("This method must be implemented by a sub-class.")

    def readByteString(self, obj, buf):
        """Returns an integer specifying the
        position of the last decoded byte in the byte array.

        This method must be overridden in a sub-class.

        arguments
        ==========
         * obj - object, The object that the byte string is being applied to.
         * buf - string in 2.5-, ByteArray in 2.6+, The bytes to be read.
        """
        
        raise ClassDefError("This method must be implemented by a sub-class.")

class _ArrayCollectionClassDef(ExternizeableClassDef):
    """A special ClassDef used internally to encode/decode an ArrayCollection."""

    ARRAY_COLLECTION_CLASS_DEF = True
    PROXY_ALIAS = 'flex.messaging.io.ArrayCollection'

    def __init__(self):
        ExternizeableClassDef.__init__(self, None, self.PROXY_ALIAS, ())

class _ObjectProxyClassDef(ExternizeableClassDef):
    """A special ClassDef used internally to encode/decode an ObjectProxy."""

    OBJECT_PROXY_CLASS_DEF = True
    PROXY_ALIAS = 'flex.messaging.io.ObjectProxy'

    def __init__(self):
        ExternizeableClassDef.__init__(self, None, self.PROXY_ALIAS, ())

# ---- module attributes ---- #

ALIAS_ATTR = '_amf_alias' # this attribute is added to a mapped class and holds the class's AMF alias.
_mapped_classes = {} # used internally to keep track of ClassDef objects.

def get_dynamic_attr_vals(obj, ignore_attrs=None, include_private=False):
    """Returns a dict of attribute values to encode.

    keys = attribute names, values = attribute values.

    argmuents
    ==========
     * obj - object, object to get dynamic attribute values from.
     * ignore_attrs - list or tuple of attributes to ignore. Default = empty list.
     * include_private - bool, if False do not include attributes that start with '_'.
          Default = False.
    """ 
    vals = {}

    if not hasattr(obj, '__dict__'):
        raise ClassDefError("Only objects with a __dict__ can be encoded dynamically.")

    if ignore_attrs is None:
        ignore_attrs = ()

    for attr, val in obj.__dict__.iteritems():
        if attr in ignore_attrs:
            continue

        if (not include_private) and (attr.startswith('_')):
            continue

        vals[attr] = val

    return vals

def map_class(class_, class_def_class, alias=None, static_attrs=None):
    """Map a class to a class_def implementation.

    arguments
    ==========
     * class_ - class, the class being mapped.
     * class_def_class - class, ClassDef or a class that inherits from ClassDef
     * alias - string, the class alias to use. Default = fully qualified Python class name.
     * static_attrs - tuple, tuple of static attribute names. Default = empty tuple.
    """
    if not hasattr(class_, '__module__'):
        raise ClassDefError("class_ argument must be a class object.")

    if not hasattr(class_def_class, 'CLASS_DEF'):
        raise ClassDefError("class_def_class argument must be class object: ClassDef or sub-class of ClassDef.")

    if static_attrs is None:
        static_attrs = ()

    if alias is None:
        alias = '.'.join(class_.__module__, class_.__name__)

    setattr(class_, ALIAS_ATTR, alias)
    class_def = class_def_class(class_, alias, static_attrs)
    _mapped_classes[alias] = class_def

def get_class_def_by_class(class_):
    """Get a ClassDef.

    Returns None in not ClassDef is found.

    arguments
    ==========
     * class_ - class, the class to find a ClassDef for.
    """
    if not hasattr(class_, ALIAS_ATTR):
        return None

    alias = getattr(class_, ALIAS_ATTR)

    if not _mapped_classes.has_key(alias):
        raise ClassDefError("ClassDef for alias '%s' could not be found." % alias)

    return _mapped_classes[alias]

def get_class_def_by_alias(alias):
    """Get a ClassDef.

    Returns None in not ClassDef is found.

    arguments
    ==========
     * alias - string, the alias to find a ClassDef for.
    """

    if not _mapped_classes.has_key(alias):
        return None

    return _mapped_classes[alias]

def unmap_class(class_):
    """Unmap a class definition.

    arguments
    ==========
     * class_ - class, the class to remove a ClassDef for.
    """
    class_def = get_class_def_by_class(class_)
    if class_def is None:
        raise ClassDefError("ClassDef not found.")

    alias = getattr(class_, ALIAS_ATTR)
    delattr(class_, ALIAS_ATTR)
    del _mapped_classes[alias]
