"""Serialize/De-serialize Python objects with AMF3."""
import calendar
from datetime import datetime

class AmFastError(Exception):
    """Base exception for this package."""
    pass

def epoch_from_date(date):
    return long(calendar.timegm(date.timetuple()) * 1000)

def date_from_epoch(epoch_secs):
    return datetime.utcfromtimestamp(epoch_secs)
