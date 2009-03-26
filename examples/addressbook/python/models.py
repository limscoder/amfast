"""Model classes for SQLAlchemy example."""

class User(object):
    def __init__(self):
        self.first_name = None
        self.last_name = None
        self.emails = []
        self.phone_numbers = []
        
class PhoneNumber(object):
    def __init__(self):
        self.label = None
        self.number = None

class Email(object):
    def __init__(self):
        self.label = None
        self.email = None

class RemoteClass(object):
    pass

class ExternClass(object):
    pass

