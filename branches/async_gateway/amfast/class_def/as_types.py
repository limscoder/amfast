"""Classes to represent Actionscript types that have no-equivalent in Python."""

import amfast

class AsByteArray(object):
    """An Actionscript ByteArray.

    If you're using 2.6+, you can use Python's
    native ByteArray type.

    attributes
    ===========
    bytes - string, bytes.
    """
    def __init__(self, bytes):
        self.bytes = bytes

class AsError(amfast.AmFastError):
    """Equivalent to: 'Error' in AS3."""

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
