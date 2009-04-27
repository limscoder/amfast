"""Functions to convert objects between PyAmf and AmFast."""

import pyamf.remoting as pyamf_remoting
import pyamf.flex.messaging as pyamf_messaging

import amfast.remoting as amfast_remoting
import amfast.remoting.flex_messages as amfast_messages

#---------- FROM PyAmf TO AmFast -----------#
def packet_to_amfast(pyamf_packet):
    print pyamf_packet.version
    print pyamf_packet.clientType

    headers = [amfast_remoting.Header(name, required=pyamf_packet.headers.is_required(name), value=header) \
        for name, header in pyamf_packet.headers]
       
    messages = [message_to_amfast(body) for body in pyamf_packet.bodies]

    return amfast_remoting.Packet(headers=headers, messages=messages)

def message_to_amfast(msg):
    if hasattr(msg, 'target'):
        target = msg.target
    else:
        target = None

    if hasattr(msg, 'status'):
        response = msg.status
    else:
        response = None

    body = flex_message_to_amfast(msg.body)

    return amfast_remoting.Message(target=target, response=response, body=body)

def flex_message_to_amfast(msg):
    if not is_instance(msg, pyamf_messaging.AbstractMessage):
        return msg

    if msg.__class__.__name__ == 'AbstractMessage':
        return amfast_messaging.AbstractMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId)

    elif msg.__class__.__name__ == 'AsyncMessage':
        return amfast_messaging.AsyncMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif msg.__class__.__name__ == 'AcknowledgeMessage':
        return amfast_messaging.AcknowledgeMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif msg.__class__.__name__ == 'CommandMessage':
        return amfast_messaging.CommandMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlation,
            operation=msg.operation)

    elif msg.__class__.__name__ == 'ErrorMessage':
        return amfast_messaging.ErrorMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId,
            extendedData=msg.extendedData, faultCode=msg.faultCode, faultDetail=msg.faultDetail,
            faultString=msg.faultString, rootCause=msg.rootCause)

    elif msg.__class__.__name__ == 'RemotingMessage':
        return amfast_messaging.RemotingMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, operation=msg.operation)

#--------- FROM AmFast to PyAmf -----------#
def packet_to_pyamf(amfast_packet):
    pass

def message_to_pyamf(msg):
    pass

def flex_message_to_pyamf(msg):
    if not is_instance(msg, amfast_messaging.AbstractMessage):
        return msg

    if msg.__class__.__name__ == 'AbstractMessage':
        return pyamf_messaging.AbstractMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId)

    elif msg.__class__.__name__ == 'AsyncMessage':
        return pyamf_messaging.AsyncMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif msg.__class__.__name__ == 'AcknowledgeMessage':
        return pyamf_messaging.AcknowledgeMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId)

    elif msg.__class__.__name__ == 'CommandMessage':
        return pyamf_messaging.CommandMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlation,
            operation=msg.operation)

    elif msg.__class__.__name__ == 'ErrorMessage':
        return pyamf_messaging.ErrorMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, correlationId=msg.correlationId,
            extendedData=msg.extendedData, faultCode=msg.faultCode, faultDetail=msg.faultDetail,
            faultString=msg.faultString, rootCause=msg.rootCause)

    elif msg.__class__.__name__ == 'RemotingMessage':
        return pyamf_messaging.RemotingMessage(body=msg.body, clientId=msg.clientId,
            destination=msg.destination, headers=msg.headers, timeToLive=msg.timeToLive,
            timestamp=msg.timestamp, messageId=msg.messageId, operation=msg.operation)
