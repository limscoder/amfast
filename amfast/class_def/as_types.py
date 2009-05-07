"""Classes to represent Actionscript types that have no-equivalent in Python."""

import amfast

class AsByteArray(object):
    """An Actionscript ByteArray.

    attributes
    ===========
    bytes - string, bytes.
    """
    
    AS_BYTE_ARRAY = True

    def __init__(self, bytes):
        self.bytes = bytes

class AsProxy(object):
    """A proxy object.

    Forces an object to be encoded as a proxy
    even if use_collection or use_proxies if False.

    attributes
    ===========
    source - object, the proxy source.
    """

    AS_PROXY = True

    def __init__(self, source=None):
        self.source = source

class AsNoProxy(object):
    """A no-proxy object.

    Forces an object to be encoded without a proxy
    even if use_collection or use_proxies is True.

    attributes
    ===========
    source - object, the no-proxy source.
    """

    AS_NO_PROXY = True

    def __init__(self, source=None):
        self.source = source

class AsError(amfast.AmFastError):
    """Equivalent to: 'Error' in AS."""

    APPLICATION_ERROR = 5000

    def __init__(self, message='', exc=None):
        self.errorID = self.APPLICATION_ERROR
        if exc is not None:
            self.name = exc.__class__.__name__
            self.message = "%s" % exc
        else:
            self.name = ''
            self.message = message

        amfast.AmFastError.__init__(self, self.message)
amfast.class_def.assign_attrs(AsError, 'Error', ('errorId', 'name', 'message'), amf3=False)
