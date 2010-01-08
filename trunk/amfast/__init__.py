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

log_debug = False # True to log verbose debug strings.
log_raw = False # True to log raw AMF byte strings.
logged_attr = '_amfast_logged' # Add to exceptions to indicate that it has been logged.
logger = logging.getLogger('AmFast')
logger.addHandler(NullHandler())
logger.setLevel(logging.DEBUG)

month_names = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def get_log_timestamp():
    dt = datetime.now()
    return '[%s/%s/%s:%s:%s:%s]' % (dt.day, month_names[dt.month - 1],
        dt.year, dt.hour, dt.minute, dt.second)

def log_exc(e):
    """Format an exception for logging."""
    if hasattr(e, logged_attr):
        return
    else:
        setattr(e, logged_attr, True)

    error_type, error_value, trbk = sys.exc_info()
    tb_list = traceback.format_tb(trbk)
    
    msg = [get_log_timestamp() + " EXCEPTION"]
    msg.append("# ---- EXCEPTION DESCRIPTION BEGIN ---- #")
    
    msg.append("# ---- Type ---- #\n%s\n# ---- Detail ---- #\n%s" % \
        (error_type.__name__, error_value))
    msg.append("# ---- Traceback ---- #")
    msg.append("-\n".join(tb_list))
    msg.append("# ---- EXCEPTION DESCRIPTION END ---- #")
    logger.error("\n".join(msg))

# --- Setup threading implementation --- #

try:
    import threading
    mutex_cls = threading.RLock
    use_dummy_threading = False
except ImportError:
    import dummy_threading
    mutex_cls = dummy_threading.RLock
    use_dummy_threading = True

    if log_debug:
        logger.debug("AmFast is using dummy_threading module.")
