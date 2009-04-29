"""Functions to convert objects between PyAmf and AmFast."""

import pyamf
import pyamf.remoting as pyamf_remoting
import pyamf.flex.messaging as pyamf_messaging

import amfast.remoting as amfast_remoting
import amfast.remoting.flex_messages as amfast_messaging

#---------- FROM PyAmf TO AmFast -----------#
def packet_to_amfast(pyamf_packet):
    if pyamf_packet.clientType == pyamf.ClientTypes.Flash6:
        client_type = amfast_remoting.Packet.FLASH_8
    elif pyamf_packet.clientType == pyamf.ClientTypes.FlashCom:
        client_type = amfast_remoting.Packet.FLASH_COM
    elif pyamf_packet.clientType == pyamf.ClientTypes.Flash9:
        client_type = amfast_remoting.Packet.FLASH_9
    else:
        clientType = amfast_remoting.Packet.FLASH_8 

    headers = [amfast_remoting.Header(name,
        required=pyamf_packet.headers.is_required(name), value=header) \
        for name, header in pyamf_packet.headers]

    messages = [message_to_amfast(body) for name, body in pyamf_packet.bodies]

    return amfast_remoting.Packet(client_type=client_type, headers=headers, messages=messages)

def message_to_amfast(msg):
    if hasattr(msg, 'target'):
        target = msg.target
    else:
        target = ''

    if hasattr(msg, 'status'):
        response = msg.status
    else:
        response = ''

    if target == 'null':
        body = (flex_message_to_amfast(msg.body[0]), )
    else:
        body = msg.body

    return amfast_remoting.Message(target=target, response=response, body=body)

def flex_message_to_amfast(msg):
    class_name = msg.__class__.__name__
    if class_name == 'AbstractMessage' or class_name == 'SmallAstractMsg':
        return amfast_messaging.AbstractMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId)

    elif class_name == 'AsyncMessage' or class_name == 'SmallAsyncMsg':
        return amfast_messaging.AsyncMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif class_name == 'AcknowledgeMessage':
        return amfast_messaging.AcknowledgeMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif class_name == 'CommandMessage' or class_name == 'SmallCommandMsg':
        return amfast_messaging.CommandMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId,
            operation=msg.operation)

    elif class_name == 'ErrorMessage':
        return amfast_messaging.ErrorMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId,
            extendedData=msg.extendedData, faultCode=msg.faultCode, faultDetail=msg.faultDetail,
            faultString=msg.faultString, rootCause=msg.rootCause)

    elif class_name == 'RemotingMessage':
        return amfast_messaging.RemotingMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, operation=msg.operation)

    return msg

#--------- FROM AmFast to PyAmf -----------#
def packet_to_pyamf(amfast_packet):
    if amfast_packet.client_type == amfast_remoting.Packet.FLASH_8:
        client_type = pyamf.ClientTypes.Flash6
        version = pyamf.AMF0
    elif amfast_packet.client_type == amfast_remoting.Packet.FLASH_COM:
        client_type = pyamf.ClientTypes.FlashCom
        version = pyamf.AMF0
    elif amfast_packet.client_type == amfast_remoting.Packet.FLASH_9:
        client_type = pyamf.ClientTypes.Flash9
        version = pyamf.AMF3
    else:
        client_type = pyamf.ClientTypes.Flash6

    packet = pyamf_remoting.Envelope()
    packet.amfVersion = version
    packet.clientType = client_type

    headers = pyamf_remoting.HeaderCollection()
    for header in amfast_packet.headers:
        headers[header.name] = header.value
        if header.required is True:
            headers.set_required(header.name, value=True)
        else:
            headers.set_required(header.name, value=False)
    packet.headers = headers

    for msg in amfast_packet.messages:
        split_target = msg.target.split('/')
        pyamf_status = '/' + split_target.pop()
        pyamf_target = '/'.join(split_target)
        packet[pyamf_target] = message_to_pyamf(msg, packet, pyamf_status) 

    return packet

def message_to_pyamf(msg, packet, status):
    try:
        if len(msg.body) == 1 and \
            isinstance(msg.body[0], amfast_messaging.AbstractMessage):
            body = (flex_message_to_pyamf(msg.body[0]), )
        else:
            body = msg.body
    except TypeError:
        if isinstance(msg.body, amfast_messaging.AbstractMessage):
            body = flex_message_to_pyamf(msg.body)
        else:
            body = msg.body

    message = pyamf_remoting.Response(body)
    message.envelope = packet

    for k, v in pyamf_remoting.STATUS_CODES.iteritems():
        if v == status:
            message.status = k
            break

    return message

def flex_message_to_pyamf(msg):
    class_name = msg.__class__.__name__
    if class_name == 'AbstractMessage':
        return pyamf_messaging.AbstractMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId)

    elif class_name == 'AsyncMessage':
        return pyamf_messaging.AsyncMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif class_name == 'AcknowledgeMessage':
        return pyamf_messaging.AcknowledgeMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif class_name == 'CommandMessage':
        return pyamf_messaging.CommandMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlation,
            operation=msg.operation)

    elif class_name == 'ErrorMessage':
        return pyamf_messaging.ErrorMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId,
            extendedData=msg.extendedData, faultCode=msg.faultCode, faultDetail=msg.faultDetail,
            faultString=msg.faultString, rootCause=msg.rootCause)

    elif class_name == 'RemotingMessage':
        return pyamf_messaging.RemotingMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, operation=msg.operation)

    return msg

#----------- PyAMF Class Extensions ------------#
# Some extra classes to smooth things along with AmFast.
class DataInputReader(object):
    """A wrapper class for pyamf.amf3.DataInput.
 
    Use this, so we can re-use our existing ISmallMsg reading code.
    """

    def __init__(self, data_input):
        self.data_input = data_input

    def read(self, length):
        return self.data_input.stream.read(length)

class PyamfAbstractSmallMsgDef(amfast_messaging.AbstractSmallMsgDef):
    """Decodes ISmallMessages with PyAmf."""

    def readExternal(self, obj, data_input):
        flags = self._readFlags(data_input)

        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.BODY_FLAG:
                    obj.body = data_input.decoder.readElement()
                else:
                    obj.body = None

                if flag & self.CLIENT_ID_FLAG:
                    obj.clientId = data_input.decoder.readElement()
                else:
                    obj.clientId = None

                if flag & self.DESTINATION_FLAG:
                    obj.destination = data_input.decoder.readElement()
                else:
                   obj.destination = None

                if flag & self.HEADERS_FLAG:
                    obj.headers = data_input.decoder.readElement()
                else:
                    obj.headers = None

                if flag & self.MESSAGE_ID_FLAG:
                    obj.messageId = data_input.decoder.readElement()
                else:
                    obj.messageId = None

                if flag & self.TIMESTAMP_FLAG:
                    obj.timestamp = data_input.decoder.readElement()
                else:
                    obj.timestamp = None

                if flag & self.TIME_TO_LIVE_FLAG:
                    obj.timeToLive = data_input.decoder.readElement()
                else:
                    obj.timeToLive = None

            if i == 1:
                if flag & self.CLIENT_ID_BYTES_FLAG:
                    clientIdBytes = data_input.decoder.readElement()
                    obj.clientId = self._readUid(clientIdBytes)
                else:
                    if not hasattr(obj, 'clientId'):
                        obj.clientId = None

                if flag & self.MESSAGE_ID_BYTES_FLAG:
                    messageIdBytes = data_input.decoder.readElement()
                    obj.messageId = self._readUid(messageIdBytes)
                else:
                    if not hasattr(obj, 'messageId'):
                        obj.messageId = None

class PyamfAsyncSmallMsgDef(amfast_messaging.AsyncSmallMsgDef):

    def readExternal(self, obj, data_input):
        PyamfAbstractSmallMsgDef.readExternal(self, obj, data_input)

        flags = self._readFlags(data_input)
        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.CORRELATION_ID_FLAG:
                    obj.correlationId = data_input.decoder.readElement()
                else:
                    obj.correlationId = None

                if flag & self.CORRELATION_ID_BYTES_FLAG:
                    correlationIdBytes = data_input.decoder.readElement()
                    obj.correlationId = self._readUid(correlationIdBytes)
                else:
                    if not hasattr(obj, 'correlationId'):
                        obj.correlationId = None

class PyamfCommandSmallMsgDef(amfast_messaging.CommandSmallMsgDef):

    def readExternal(self, obj, data_input):
        PyamfAsyncSmallMsgDef.readExternal(self, obj, data_input)

        flags = self._readFlags(data_input)
        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.OPERATION_FLAG:
                    obj.operation = data_input.decoder.readElement()
                else:
                    obj.operation = None

class SmallAbstractMsg(pyamf_messaging.AbstractMessage):
    """A sub-class of AbstractMessage that can encode itself using ISmallMsg."""

    CLASS_DEF = None

    def _getClassDef(self):
        if (self.CLASS_DEF is None):
            self.CLASS_DEF = amfast_messaging.PyamfAbstractSmallMsgDef(self.__class__)
        return self.CLASS_DEF
    class_def = property(_getClassDef)

    def __readamf__(self, data_input):
        return self.class_def.readExternal(self, DataInputReader(data_input))

    def __writeamf__(self, data_output):
        raise pyamf.EncodeError("__writeamf__ is not implemented for this class.")

class SmallAsyncMsg(pyamf_messaging.AsyncMessage):
    CLASS_DEF = None

    def _getClassDef(self):
        if (self.CLASS_DEF is None):
            self.CLASS_DEF = amfast_messaging.PyamfAsyncSmallMsgDef(self.__class__)
        return self.CLASS_DEF
    class_def = property(_getClassDef)

    def __readamf__(self, data_input):
        return self.class_def.readExternal(self, DataInputReader(data_input))

    def __writeamf__(self, data_output):
        raise pyamf.EncodeError("__writeamf__ is not implemented for this class.")

pyamf.register_class(SmallAsyncMsg, 'DSA',
    attrs=[
        'body', 'clientId', 'destination', 'headers', 'messageId',
        'timeToLive', 'timestamp', 'correlationId'
    ], metadata=['amf3', 'external'])


class SmallCommandMsg(pyamf_messaging.CommandMessage):
    CLASS_DEF = None

    def _getClassDef(self):
        if (self.CLASS_DEF is None):
            self.CLASS_DEF = amfast_messaging.PyamfCommandSmallMsgDef(self.__class__)
        return self.CLASS_DEF
    class_def = property(_getClassDef)

    def __readamf__(self, data_input):
        return self.class_def.readExternal(self, DataInputReader(data_input))

    def __writeamf__(self, data_output):
        raise pyamf.EncodeError("__writeamf__ is not implemented for this class.")

pyamf.register_class(SmallCommandMsg, 'DSC',
    attrs=[
        'body', 'clientId', 'destination', 'headers', 'messageId',
        'timeToLive', 'timestamp', 'correlationId', 'operation'
    ], metadata=['amf3', 'external'])
