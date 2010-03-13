"""Provides an interface for determining how Python objects are serialized and de-serialized."""
import threading

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
     * alias - string, the AMF alias name of the mapped class
     * static_attrs - tuple or list, a tuple of static attribute names,
          all values must be strings or unicode.
     * amf3 - bool, if True, this object will be encoded in AMF3.
     * encode_types - dict, keys = attribute names, values = callables.
         Callables must accept a single parameter
         (the object being encoded) and return a new object.
     * decode_types - dict, keys = attribute names, values = callables.
         Callables must accept a single parameter
         (the object being decoded) and return a new object.

    """

    CLASS_DEF = True

    def __init__(self, class_, alias=None, static_attrs=None,
        amf3=None, encode_types=None, decode_types=None, _built_in=False):
        """arguments
        =============
         * class_ - class, the class being mapped.
         * alias - string, specifies the amf class alias. Default = module.class
         * static_attrs - tuple or list, a tuple of static attribute strings. Default = empty tuple
         * amf3 - bool, if True, this object will be encoded in AMF3. Default = True
         * encode_types - dict, keys = attribute names, values = callables. Default = None
         * decode_types - dict, keys = attribute names, values = callables. Default = None
        """
        self.class_ = class_
        self._built_in = _built_in

        if alias is None:
            if hasattr(class_, ALIAS):
                alias = getattr(class_, ALIAS)
            else:
                alias = '.'.join((class_.__module__, class_.__name__))
        self.alias = alias

        if static_attrs is None:
            if hasattr(class_, STATIC_ATTRS):
                static_attrs = self.static_attrs = getattr(class_, STATIC_ATTRS)
            else: 
                static_attrs = () 
        self.static_attrs = static_attrs

        if amf3 is None:
            if hasattr(class_, AMF3):
                amf3 = getattr(class_, AMF3)
            else:
                amf3 = True
        self.amf3 = amf3

        self.encode_types = encode_types
        self.decode_types = decode_types

    def getStaticAttrVals(self, obj):
        """Returns a list of values of attributes defined in self.static_attrs

        If this method is overridden to provide custom behavior, please note:
        Returned values MUST BE IN THE SAME ORDER AS THEY APPEAR IN self.static_attrs.

        arguments
        ==========
         * obj - object, the object to get attribute values from.
        """
        return [getattr(obj, attr, None) for attr in self.static_attrs]

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
        [setattr(obj, key, val) for key, val in vals.iteritems()]

class DynamicClassDef(ClassDef):
    """A ClassDef with dynamic attributes."""

    DYNAMIC_CLASS_DEF = True

    def __init__(self, class_, alias=None, static_attrs=None, amf3=True,
        encode_types=None, decode_types=None, include_private=None, _built_in=False):
        ClassDef.__init__(self, class_, alias, static_attrs, amf3,
            encode_types, decode_types, _built_in)

        self.include_private = include_private

    def getDynamicAttrVals(self, obj, include_private=False):
        """Returns a dict where keys are attribute names and values are attribute values.

        arguments
        ==========
        obj - object, the object to get attributes for.
        include_private - bool, if False do not include attributes with
            names starting with '_'. Default = False.
        """
        if self.include_private is None:
            ip = include_private
        else:
            ip = self.include_private

        return get_dynamic_attr_vals(obj, self.static_attrs, ip);

class ExternClassDef(ClassDef):
    """A ClassDef where the byte string encoding/decoding is customized.
   
    The Actionscript version of the class must implement IExternalizeable.
    """
    
    EXTERNALIZABLE_CLASS_DEF = True
    
    def __init__(self, class_, alias=None, static_attrs=None, _built_in=False):
        ClassDef.__init__(self, class_, alias, static_attrs, amf3=True,
            _built_in=_built_in)
 
    def writeExternal(self, obj, context):
        """
        This method must be overridden in a sub-class.

        arguments
        ==========
         * obj - object, The object that is being encoded.
         * context - amfast.decoder.EncoderContext, holds encoding related properties.
        """
        raise ClassDefError("This method must be implemented by a sub-class.")

    def readExternal(self, obj, context):
        """
        This method must be overridden in a sub-class.

        arguments
        ==========
         * obj - object, The object that the byte string is being applied to.
         * context - amfast.decoder.DecoderContext, holds decoding related properties.
        """
        raise ClassDefError("This method must be implemented by a sub-class.")

class _ProxyClassDef(ExternClassDef):
    """A special class used internally to encode/decode Proxied objects."""

    PROXY_CLASS_DEF = True
    PROXY_ALIAS = 'proxy'

    class _ProxyObject(object):
        """Empty class used for mapping."""
        pass

    def __init__(self):
        ExternClassDef.__init__(self, self._ProxyObject, self.PROXY_ALIAS,
            None, _built_in=True)

class _ArrayCollectionClassDef(_ProxyClassDef):
    """A special ClassDef used internally to encode/decode an ArrayCollection."""

    ARRAY_COLLECTION_CLASS_DEF = True
    PROXY_ALIAS = 'flex.messaging.io.ArrayCollection'

    def __init__(self):
        _ProxyClassDef.__init__(self)

class _ObjectProxyClassDef(_ProxyClassDef):
    """A special ClassDef used internally to encode/decode an ObjectProxy."""

    OBJECT_PROXY_CLASS_DEF = True
    PROXY_ALIAS = 'flex.messaging.io.ObjectProxy'

    def __init__(self):
        _ProxyClassDef.__init__(self)

class ClassDefMapper(object):
    """Map classes to ClassDefs, retrieve class_defs by class or alias name."""
    def __init__(self):
        """
        arguments
        ==========
        * class_def_attr - string, an attribute with this name will be added
            mapped classes. Default = '_amf_alias'
        """

        self._lock = threading.RLock()
        self._mapped_classes = {}
        self._mapped_aliases = {}
        self._mapBuiltIns()

    def __iter__(self):
        return self._mapped_aliases.itervalues()

    def _mapBuiltIns(self):
        """Map built-in ClassDefs for default behavior."""
        from as_types import AsError
        from amfast.remoting import flex_messages as messaging

        # Proxy objects
        self.mapClass(_ArrayCollectionClassDef())
        self.mapClass(_ObjectProxyClassDef())

        # Exceptions
        self.mapClass(ClassDef(AsError, _built_in=True))
        self.mapClass(ClassDef(messaging.FaultError, _built_in=True))

        # Flex remoting messages
        self.mapClass(ClassDef(messaging.RemotingMessage, _built_in=True))
        self.mapClass(messaging.AsyncSmallMsgDef(messaging.AsyncMessage,
            alias="DSA", _built_in=True))
        self.mapClass(ClassDef(messaging.AsyncMessage, _built_in=True))
        self.mapClass(messaging.CommandSmallMsgDef(messaging.CommandMessage,
            alias="DSC", _built_in=True))
        self.mapClass(ClassDef(messaging.CommandMessage, _built_in=True))
        self.mapClass(ClassDef(messaging.AcknowledgeMessage, _built_in=True))
        self.mapClass(ClassDef(messaging.ErrorMessage, _built_in=True))

    def mapClass(self, class_def):
        """Map a class_def implementation, so that it can be retrieved based on class attributes.

        arguments
        ==========
         * class_def - ClassDef, ClassDef being mapped.
        """
        if not hasattr(class_def, 'CLASS_DEF'):
            raise ClassDefError("class_def argument must be a ClassDef object.")

        self._lock.acquire()
        try:
            self._mapped_classes[class_def.class_] = class_def
            self._mapped_aliases[class_def.alias] = class_def
        finally:
            self._lock.release()

    def getClassDefByClass(self, class_):
        """Get a ClassDef.

        Returns None if ClassDef is not found.

        arguments
        ==========
         * class_ - class, the class to find a ClassDef for.
        """
        return self._mapped_classes.get(class_, None)

    def getClassDefByAlias(self, alias):
        """Get a ClassDef.

        Returns None in not ClassDef is found.

        arguments
        ==========
         * alias - string, the alias to find a ClassDef for.
        """
        return self._mapped_aliases.get(alias, None)

    def unmapClass(self, class_):
        """Unmap a class definition.

        arguments
        ==========
         * class_ - class, the class to remove a ClassDef for.
        """
        self._lock.acquire()
        try:
            for alias, klass in self._mapped_aliases.iteritems():
                if class_ == klass:
                    del self._mapped_aliases[alias]

            class_id = id(class_)
            if class_id in self._mapped_classes:
                del self._mapped_classes[class_id]
        finally:
            self._lock.release()

# ---- module attributes ---- #

def get_dynamic_attr_vals(obj, ignore_attrs=None, include_private=False):
    """Returns a dict of attribute values to encode.

    keys = attribute names, values = attribute values.

    argmuents
    ==========
     * obj - object, object to get dynamic attribute values from.
     * ignore_attrs - list or tuple of attributes to ignore. Default = empty tuple.
     * include_private - bool, if False do not include attributes that start with '_'.
          Default = False.
    """ 
    vals = {}

    for attr, val in obj.__dict__.iteritems():
        if ignore_attrs is not None:
            if attr in ignore_attrs:
                continue

        if (include_private is False) and (attr.startswith('_')):
            continue

        vals[attr] = val

    return vals

# These properties can be set on a class
# to map attributes within the class.
ALIAS = '_AMFAST_ALIAS'
STATIC_ATTRS = '_AMFAST_STATIC_ATTRS'
AMF3 = '_AMFAST_AMF3'

def assign_attrs(class_, alias=None, static_attrs=None, amf3=None):
    """
    Use to map ClassDef attributes to a class. Useful if you want to keep
    ClassDef configuration with the class being mapped, instead of at 
    the point where the ClassDef is created.

    If you assign ClassDef attributes with this method, you can
    call ClassDef(class_) to create a ClassDef, and the assigned
    attributes will be applied to the new ClassDef.

    Arguments provided to the ClassDef() will override attributes
    that were assigned with this function.

    arguments
    ==========
     * class_ - class, the class to assign attributes to.
     * alias - string, the amf alias name of the mapped class
     * static_attrs - tuple, a tuple of static attribute names, all values must be strings or unicode
     * amf3 - bool, if True, this object will be encoded in AMF3.
    """
    if alias is not None:
        setattr(class_, ALIAS, alias)

    if static_attrs is not None:
        setattr(class_, STATIC_ATTRS, static_attrs)

    if amf3 is not None:
        setattr(class_, AMF3, amf3)
