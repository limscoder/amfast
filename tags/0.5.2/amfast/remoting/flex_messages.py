"""Equivalent to Flex mx.messaging.messages package."""
import uuid
import time
import cgi

import amfast
from amfast import class_def, remoting
from amfast.class_def.as_types import AsError

try:
    # Use decode module if available.
    # Users may be using PyAmf instead.
    from amfast.decode import decode
except ImportError:
    pass

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
    """Base class for all FlexMessages."""

    DESTINATION_CLIENT_ID_HEADER = 'DSDstClientId'
    ENDPOINT_HEADER = 'DSEndpoint'
    FLEX_CLIENT_ID_HEADER = 'DSId'
    PRIORITY_HEADER = 'DSPriority'
    REMOTE_CREDENTIALS_CHARSET_HEADER = 'DSRemoteCredentialsCharset'
    REMOTE_CREDENTIALS_HEADER = 'DSRemoteCredentials'
    REQUEST_TIMEOUT_HEADER = 'DSRequestTimeout'
    STATUS_CODE_HEADER = 'DSStatusCode'

    def __init__(self, body=None, clientId=None, destination=None,
        headers=None, timeToLive=None, timestamp=None, messageId=None):
        self.body = body
        self.clientId = clientId
        self.destination = destination
        self.timeToLive = timeToLive

        if headers is not None:
            self.headers = headers

        if timestamp is None:
            timestamp = time.time() * 1000
        self.timestamp = timestamp
   
        if messageId is None:
            messageId = self._getId()
        self.messageId = messageId

    def invoke(self, packet, msg):
        """Invoke all message headers."""
        if amfast.log_debug:
            amfast.logger.debug("\nInvoking FlexMessage:\n%s" % self)

    def fail(self, packet, msg, exc):
        """Return an error message."""
        fault = FaultError(exc=exc)
        response = ErrorMessage(exc=fault)
        self._matchAcknowledge(packet, msg, response)
        return response

    def convertFail(self, exc):
        """Convert this message to an error."""
        fault = FaultError(exc=exc)
        headers = getattr(self, 'headers', None)
        return ErrorMessage(self, clientId=self.clientId, destination=self.destination,
            headers=headers, timeToLive=self.timeToLive, timestamp=self.timestamp,
            messageId=self.messageId, correlationId=self.correlationId, exc=fault)

    def getAcknowledgeClass(self):
        """Returns the correct class for the response message."""
        return AcknowledgeMessage

    def acknowledge(self, packet, msg):
        """Return a successful result message."""
        class_ = self.getAcknowledgeClass()
        response = class_()
        self._matchAcknowledge(packet, msg, response)
        return response

    def _matchAcknowledge(self, packet, msg, response):
        """Syncs values between this message and it's response acknowledgement."""
        response.correlationId = self.messageId

        if self.clientId is None:
            self.clientId = packet.channel.channel_set.connection_manager.generateId()
        response.clientId = self.clientId

    def _getId(self):
        """Get a messageId or clientId."""
        return str(uuid.uuid4())

    def __str__(self):
        header_str = ''
        if hasattr(self, 'headers') and self.headers is not None:
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

class AbstractSmallMsgDef(class_def.ExternClassDef):
    """Encodes and decodes messages using ISmallMessage.

    ISmallMessages use a more compact representation
    of mx.messaging.messages.
    """

    HAS_NEXT_FLAG = 0x80
    BODY_FLAG = 0x01
    CLIENT_ID_FLAG = 0x02
    DESTINATION_FLAG = 0x04
    HEADERS_FLAG = 0x08
    MESSAGE_ID_FLAG = 0x10
    TIMESTAMP_FLAG = 0x20
    TIME_TO_LIVE_FLAG = 0x40
    CLIENT_ID_BYTES_FLAG = 0x01
    MESSAGE_ID_BYTES_FLAG = 0x02

    ALPHA_CHAR_CODES = (48, 49, 50, 51, 52, 53, 54, 
        55, 56, 57, 65, 66, 67, 68, 69, 70)

    def _readUid(self, bytes):
        """Decode a 128bit byte array into a 36 char string representing an UID."""
        if bytes is None:
            return None

        if hasattr(bytes, 'bytes'):
            # amfast.class_def.as_types.ByteArray object
            byte_str = bytes.bytes
        else:
            # Other type
            byte_str = str(bytes)

        if len(byte_str) != 16:
           return None

        uid_chars = [None] * 36
        idx = 0
        for i, byte in enumerate(byte_str):
            if i == 4 or i == 6 or i == 8 or i == 10:
                # hyphen
                uid_chars[idx] = 45
                idx += 1

            char_code = ord(byte)
            uid_chars[idx] = self.ALPHA_CHAR_CODES[(char_code & 0xF0) >> 4]
            idx += 1
            uid_chars[idx] = self.ALPHA_CHAR_CODES[(char_code & 0x0F)]
            idx += 1
        return ''.join([chr(byte) for byte in uid_chars])

    def _readFlags(self, context):
        """Reads flags."""
        flags = []

        flag = self.HAS_NEXT_FLAG
        while (flag & self.HAS_NEXT_FLAG):
            flag = ord(context.read(1))
            flags.append(flag)

        return flags

    def readExternal(self, obj, context):
        flags = self._readFlags(context)

        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.BODY_FLAG:
                    obj.body = decode(context)
                else:
                    obj.body = None

                if flag & self.CLIENT_ID_FLAG:
                    obj.clientId = decode(context)
                else:
                    obj.clientId = None

                if flag & self.DESTINATION_FLAG:
                    obj.destination = decode(context)
                else:
                   obj.destination = None

                if flag & self.HEADERS_FLAG:
                    obj.headers = decode(context)
                else:
                    obj.headers = None

                if flag & self.MESSAGE_ID_FLAG:
                    obj.messageId = decode(context)
                else:
                    obj.messageId = None

                if flag & self.TIMESTAMP_FLAG:
                    obj.timestamp = decode(context)
                else:
                    obj.timestamp = None

                if flag & self.TIME_TO_LIVE_FLAG:
                    obj.timeToLive = decode(context)
                else:
                    obj.timeToLive = None

            if i == 1:
                if flag & self.CLIENT_ID_BYTES_FLAG:
                    clientIdBytes = decode(context)
                    obj.clientId = self._readUid(clientIdBytes)
                else:
                    if not hasattr(obj, 'clientId'):
                        obj.clientId = None

                if flag & self.MESSAGE_ID_BYTES_FLAG:
                    messageIdBytes = decode(context)
                    obj.messageId = self._readUid(messageIdBytes)
                else:
                    if not hasattr(obj, 'messageId'):
                        obj.messageId = None

class RemotingMessage(AbstractMessage):

    def __init__(self, body=None, clientId=None, destination=None,
        headers=None, timeToLive=None, timestamp=None, messageId=None,
        operation=None, source=None):

        AbstractMessage.__init__(self, body=body, clientId=clientId,
            destination=destination, headers=headers, timeToLive=timeToLive,
            timestamp=timestamp, messageId=messageId)

        self.operation = operation
        self.source = source

    def invoke(self, packet, msg):
        AbstractMessage.invoke(self, packet, msg)

        # Set connection object, so it is accessable in target.
        self.connection = packet.channel.getFlexConnection(self)

        target = packet.channel.channel_set.service_mapper.getTarget(self.destination, self.operation)        
        if target is None:
            raise FlexMessageError("Operation '%s' not found." % \
                remoting.Service.SEPARATOR.join((self.destination, self.operation)))

        if target.secure is True:
            if self.connection.authenticated is False:
                from amfast.remoting.channel import SecurityError
                raise SecurityError("Operation requires authentication.")

        msg.response_msg.body.body = target.invoke(packet, msg, self.body)

class_def.assign_attrs(RemotingMessage, 'flex.messaging.messages.RemotingMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'source', 'operation'), True)

class AsyncMessage(AbstractMessage):

    SUBTOPIC_HEADER = 'DSSubtopic'

    def __init__(self, body=None, clientId=None, destination=None,
        headers=None, timeToLive=None, timestamp=None, messageId=None,
        correlationId=None):
 
               
        AbstractMessage.__init__(self, body=body, clientId=clientId,
            destination=destination, headers=headers, timeToLive=timeToLive,
            timestamp=timestamp, messageId=messageId) 

        if correlationId is not None:
            self.correlationId = correlationId

    def invoke(self, packet, msg):
        """Publish this message."""

        AbstractMessage.invoke(self, packet, msg)

        channel = packet.channel
        channel_set = channel.channel_set
        self.connection = channel.getFlexConnection(self)

        if channel_set.subscription_manager.secure is True:
            if self.connection.authenticated is False:
                from amfast.remoting.channel import SecurityError
                raise SecurityError("Operation requires authentication.")

        channel_set.publishMessage(self)

class_def.assign_attrs(AsyncMessage, 'flex.messaging.messages.AsyncMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId'), True)

class AsyncSmallMsgDef(AbstractSmallMsgDef):
    """Decodes messages that were encoded using ISmallMessage."""

    CORRELATION_ID_FLAG = 0x01
    CORRELATION_ID_BYTES_FLAG = 0x02

    def readExternal(self, obj, context):
        AbstractSmallMsgDef.readExternal(self, obj, context)

        flags = self._readFlags(context)
        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.CORRELATION_ID_FLAG:
                    obj.correlationId = decode(context)
                else:
                    obj.correlationId = None

                if flag & self.CORRELATION_ID_BYTES_FLAG:
                    correlationIdBytes = decode(context)
                    obj.correlationId = self._readUid(correlationIdBytes)
                else:
                    if not hasattr(obj, 'correlationId'):
                        obj.correlationId = None

class CommandMessage(AsyncMessage):
    """A Flex CommandMessage. Operations are integers instead of strings.

    See Flex API docs for list of possible commands.
    """

    SUBSCRIBE_OPERATION = 0
    UNSUBSCRIBE_OPERATION = 1
    POLL_OPERATION = 2
    CLIENT_SYNC_OPERATION = 4
    CLIENT_PING_OPERATION = 5
    CLUSTER_REQUEST_OPERATION = 7
    LOGIN_OPERATION = 8
    LOGOUT_OPERATION = 9
    SUBSCRIPTION_INVALIDATE_OPERATION = 10
    MULTI_SUBSCRIBE_OPERATION = 11
    DISCONNECT_OPERATION = 12
    TRIGGER_CONNECT_OPERATION = 13

    ADD_SUBSCRIPTIONS = 'DSAddSub'
    CREDENTIALS_CHARSET_HEADER = 'DSCredentialsCharset'
    MAX_FREQUENCY_HEADER = 'DSMaxFrequency'
    MESSAGING_VERSION = 'DSMessagingVersion'
    NEEDS_CONFIG_HEADER = 'DSNeedsConfig'
    NO_OP_POLL_HEADER = 'DSNoOpPoll'
    POLL_WAIT_HEADER = 'DSPollWait'
    PRESERVE_DURABLE_HEADER = 'DSPreserveDurable'
    REMOVE_SUBSCRIPTIONS = 'DSRemSub'
    SELECTOR_HEADER = 'DSSelector'
    SUBTOPIC_SEPARATOR = '_;_'

    def __init__(self,  body=None, clientId=None, destination=None,
        headers=None, timeToLive=None, timestamp=None, messageId=None,
        correlationId=None, operation=1000):

        AsyncMessage.__init__(self, body=body, clientId=clientId,
            destination=destination, headers=headers, timeToLive=timeToLive,
            timestamp=timestamp, messageId=messageId, correlationId=correlationId)

        self.operation = operation

    def invoke(self, packet, msg):
        AbstractMessage.invoke(self, packet, msg)

        self.connection = packet.channel.getFlexConnection(self)

        target = packet.channel.channel_set.service_mapper.command_service.getTarget(self.operation)
        if target is None:
            raise FlexMessageError("Command '%s' not found." % self.operation)

        msg.response_msg.body.body = target.invoke(packet, msg, (self.body,))

    def getAcknowledgeClass(self):
        """Returns the correct class for the response message."""
        if self.operation == self.POLL_OPERATION:
            return CommandMessage

        return AsyncMessage.getAcknowledgeClass(self)

class_def.assign_attrs(CommandMessage, 'flex.messaging.messages.CommandMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId',
        'operation'), True)

class CommandSmallMsgDef(AsyncSmallMsgDef):
    """Decodes messages that were encoded using ISmallMessage."""

    OPERATION_FLAG = 0x01

    def readExternal(self, obj, context):
        AsyncSmallMsgDef.readExternal(self, obj, context)

        flags = self._readFlags(context)
        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.OPERATION_FLAG:
                    obj.operation = decode(context)
                else:
                    obj.operation = None

class AcknowledgeMessage(AsyncMessage):
    """A response message sent back to the client."""

    ERROR_HINT_HEADER = 'DSErrorHint'

class_def.assign_attrs(AcknowledgeMessage, 'flex.messaging.messages.AcknowledgeMessage',
    ('body', 'clientId', 'destination', 'headers',
        'messageId', 'timestamp', 'timeToLive', 'correlationId'), True)

class ErrorMessage(AcknowledgeMessage):
    """A response message sent back to the client after a failure."""

    def __init__(self, body=None, clientId=None, destination=None,
        headers=None, timeToLive=None, timestamp=None, messageId=None,
        correlationId=None, exc=None, faultCode='', faultString='',
        faultDetail='', rootCause=None, extendedData=None):
        """exc must be a FaultError or None."""
       
        AcknowledgeMessage.__init__(self, body=body, clientId=clientId,
            destination=destination, headers=headers, timeToLive=timeToLive,
            timestamp=timestamp, messageId=messageId, correlationId=correlationId)

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

class StreamingMessage(CommandMessage):
    """A command message delivered over an HTTP streaming channel."""

    # streaming command key
    COMMAND_PARAM_NAME = 'command'

    # open a streaming connection
    OPEN_COMMAND = 'open'

    # close streaming connection
    CLOSE_COMMAND = 'close'

    # stream id
    ID_PARAM_NAME = 'streamId'

    # stream version
    VERSION_PARAM_NAME = 'version'

    # Bytes for encoding message
    CR_BYTE = 13
    LF_BYTE = 10
    NULL_BYTE = 0

    @classmethod
    def getDisconnectMsg(cls):
        msg = CommandMessage()
        msg.operation = CommandMessage.DISCONNECT_OPERATION
        return msg

    @classmethod
    def prepareMsg(cls, msg, endpoint):
        return cls.getMsgBytes(endpoint.encode(msg, amf3=True))

    @classmethod
    def getMsgBytes(cls, raw):
        """Add size information to raw AMF encoding for streaming."""
        byte_size = len(raw)
        hex_len = '%x' % byte_size # Turn length into a string of hex digits
        return ''.join((hex_len, chr(cls.CR_BYTE), chr(cls.LF_BYTE), raw)) # CR_BYTE marks end of size declaration, LF_BYTE marks beginning of data section.

    def parseArgs(self, args):
        if not hasattr(self, 'headers') or self.headers is None:
            self.headers = {}
        
        if self.FLEX_CLIENT_ID_HEADER in args:
            self.headers[self.FLEX_CLIENT_ID_HEADER] = args[self.FLEX_CLIENT_ID_HEADER][0]

        if self.COMMAND_PARAM_NAME in args:
            self.operation = args[self.COMMAND_PARAM_NAME][0]

    def parseParams(self, url_params):
        """Parses and sets attributes from URL parameters."""
        params = cgi.parse_qs(url_params, True)
        self.operation = params.get(self.COMMAND_PARAM_NAME)[0]

    def parseBody(self, body):
        if not hasattr(self, 'headers') or self.headers is None:
            self.headers = {}

        params = cgi.parse_qsl(body, True)
        for param in params:
            if param[0] == self.FLEX_CLIENT_ID_HEADER:
                self.headers[self.FLEX_CLIENT_ID_HEADER] = param[1]

    def acknowledge(self, *args, **kwargs):
        """Return a successful result message."""
        class_ = self.getAcknowledgeClass()
        response = class_()
        self._matchAcknowledge(response)
        return response

    def _matchAcknowledge(self, response, *args, **kwargs):
        """Syncs values between this message and it's response acknowledgement."""
        response.correlationId = self.operation
