"""Serialize/De-serialize Python objects with AMF3."""
import sys
import traceback
import calendar
from datetime import datetime
import logging

class AmFastError(Exception):
    """Base exception for this package."""
    pass

def epoch_from_date(date):
    return long(calendar.timegm(date.timetuple()) * 1000)

def date_from_epoch(epoch_secs):
    return datetime.utcfromtimestamp(epoch_secs)

# --- setup module level logging --- #

class NullHandler(logging.Handler):
    """A logging handler that does nothing, so that end-users
    do not receive 'No handlers could be found...' warning.
 
    Yes, this is the way the Python docs recommend solving this problem.
    """
    def emit(self, record):
        pass

log_debug = True
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
