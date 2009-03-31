"""Equivalent to mx.messaging.messages package."""
import uuid
import calendar
import time

import amfast
from amfast import class_def, remoting
from amfast.class_def.as_types import AsError

class FlexMessageError(remoting.RemotingError):
    """Errors raised by this module."""
    pass

class FaultError(AsError):
    """Equivalent to mx.rpc.Fault."""

    def __init__(self, message='', exc=None, detail='', content=None):
        AsError.__init__(self, message, exc)
        
        self.faultCode = self.name
        self.faultString = self.message
        self.faultDetail = detail
        self.rootCause = exc
        self.content = content
class_def.assign_attrs(FaultError, 'mx.rpc.Fault',
    ('errorId', 'name', 'message', 'faultCode',
        'faultString', 'faultDetail', 'rootCause', 'content'), True)

class AbstractMessage(object):
    """Base class for all flex messages."""

    def __init__(self):
        self.body = None
        self.clientId = None
        self.destination = None
        self.headers = None
        self.messageId = None
        self.timestamp = None

    def invoke(self, packet, msg):
        """Invoke all message headers."""
        if amfast.log_debug:
            amfast.logger.debug("Invoking FlexMessage:\n%s" % self)

        if self.headers is not None:
            for name, val in self.headers.iteritems():
                target = packet.gateway.service_mapper.message_header_service.getTargetByName(name)
                if target is not None:
                    return target.invoke(packet, msg, (val,))

    def fail(self, exc):
        """Return an error message."""
        fault = FaultError(exc=exc)
        response = ErrorMessage(exc=fault)
        self._matchAcknowledge(response)
        return response

    def acknowledge(self):
        """Return a successful result message."""
        response = AcknowledgeMessage()
        self._matchAcknowledge(response)
        return response

    def _matchAcknowledge(self, response):
        """Syncs values between this message and it's response acknowledgement."""
        response.messageId = self._getId()
        response.timestamp = calendar.timegm(time.gmtime())
        response.correlationId = self.messageId

    def _getId(self):
        """Get a messageId or clientId."""
        return str(uuid.uuid4())

    def __str__(self):
        header_str = ''
        if self.headers is not None:
            header_str = '\n  '.join(["<header name=\"%s\">%s</header>" % (key, val) for key, val in self.headers.iteritems()])
        
        attrs = {}
        for key, val in self.__dict__.iteritems():
            if key == 'body':
                continue
            if key == 'headers':
                continue
            attrs[key] = val
        
        attrs_str = '\n  '.join(["<attr name=\"%s\">%s</attr>" % (key, val) for key, val in attrs.iteritems()])

        str = """
<FlexMessage: %s>
 <headers>
  %s
 </headers>

 <body>
  %s
 </body>

 <attributes>
  %s
 </attributes>
</FlexMessage>
""" % (self.__class__.__name__, header_str, self.body, attrs_str)
        return str

class_def.assign_attrs(AbstractMessage, 'flex.messaging.messages.AbstractMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive'), True)

class RemotingMessage(AbstractMessage):

    def __init__(self):
        AbstractMessage.__init__(self)
        self.operation = None
        self.source = None

    def invoke(self, packet, msg):
        AbstractMessage.invoke(self, packet, msg)

        target = packet.gateway.service_mapper.getTargetByName(self.destination, self.operation)
        if target is None:
            raise FlexMessageError("Operation '%s' not found." % \
                remoting.Service.SEPARATOR.join((self.destination, self.operation)))
        msg.response_msg.value.body = target.invoke(packet, msg, self.body)

class_def.assign_attrs(RemotingMessage, 'flex.messaging.messages.RemotingMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'source', 'operation'), True)

class AsyncMessage(AbstractMessage):

    def __init__(self):
        AbstractMessage.__init__(self)
        self.correlationId = None

    def invoke(self, packet, msg):
        AbstractMessage.invoke(self, packet, msg)
        return True

class_def.assign_attrs(AsyncMessage, 'flex.messaging.messages.AsyncMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId'), True)

class CommandMessage(AsyncMessage):
    """A Flex CommandMessage. Operations are integers instead of strings.
    See Flex API docs for list of possible commands.
    """

    SUBSCRIBE_OPERATION = 0
    CLIENT_PING_OPERATION = 5

    def __init__(self, operation=''):
        AsyncMessage.__init__(self)
        self.operation = operation

    def invoke(self, packet, msg):
        AbstractMessage.invoke(self, packet, msg)

        target = packet.gateway.service_mapper.command_service.getTargetByName(self.operation)
        if target is None:
            raise FlexMessageError("Command '%s' not found." % self.operation)
        msg.response_msg.value.body = target.invoke(packet, msg, self.body)

class_def.assign_attrs(CommandMessage, 'flex.messaging.messages.CommandMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId',
        'operation'), True)

class AcknowledgeMessage(AsyncMessage):
    """A response message sent back to the client."""

    def __init__(self):
        AsyncMessage.__init__(self)
class_def.assign_attrs(AcknowledgeMessage, 'flex.messaging.messages.AcknowledgeMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId'), True)

class ErrorMessage(AcknowledgeMessage):
    """A response message sent back to the client after a failure."""

    def __init__(self, exc=None, faultCode='', faultString='',
        faultDetail='', rootCause=None, extendedData=None):
        """exc must be a FaultError or None."""
       
        AcknowledgeMessage.__init__(self)

        if exc is not None:
            self.faultCode = exc.faultCode
            self.faultString = exc.faultString
            self.faultDetail = exc.faultDetail
            self.rootCause = exc.rootCause
            self.extendedData = exc.content
            self.body = exc
        else:
            self.faultCode = faultCode
            self.faultString = faultString
            self.faultDetail = faultDetail
            self.rootCause = rootCause
            self.extendedData = extendedData

class_def.assign_attrs(ErrorMessage, 'flex.messaging.messages.ErrorMessage', 
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId', 'faultCode',
        'faultString', 'faultDetail', 'rootCause', 'extendedData'), True)
