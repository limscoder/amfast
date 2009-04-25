"""Serialize/De-serialize Python objects with AMF3."""
import sys
import traceback
import calendar
from datetime import datetime
import logging

class AmFastError(Exception):
    """Base exception for this package."""
    # To get around 2.6 deprecation warning
    def _get_message(self):
        return self._message
    def _set_message(self, message):
        self._message = message
    message = property(_get_message, _set_message)

def epoch_from_date(date):
    """Returns epoch milliseconds."""
    return long(calendar.timegm(date.timetuple()) * 1000)

def date_from_epoch(epoch_secs):
    """Returns datetime."""
    return datetime.utcfromtimestamp(epoch_secs)

def format_byte_string(byte_string):
    """Get a human readable description of a byte string."""
    bytes = []
    for i, x in enumerate(byte_string):
        val = ord(x)
        char = ''
        if val > 31 and val < 127:
            char = "%s" % x
        bytes.append("%d: %d-%02X-'%s'" % (i, val, val, char))
    return ' '.join(bytes)

# --- setup module level logging --- #

class NullHandler(logging.Handler):
    """A logging handler that does nothing, so that end-users
    do not receive 'No handlers could be found...' warning.
 
    Yes, this is the way the Python docs recommend solving this problem.
    """
    def emit(self, record):
        pass

log_debug = False
logger = logging.getLogger('AmFast')
logger.addHandler(NullHandler())
logger.setLevel(logging.DEBUG)

def log_exc():
    """Log an exception."""
    error_type, error_value, trbk = sys.exc_info()
    tb_list = traceback.format_tb(trbk)
    msg = "Exception: %s -\n-\nDescription: %s -\n-\nTraceback: " %\
        (error_type.__name__, error_value)
    msg += "-\n".join(tb_list)
    logger.error(msg)
