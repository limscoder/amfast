"""Classes to represent Actionscript types that have no-equivalent in Python."""

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
