"""Built in Target functions."""

import uuid

from amfast.class_def.as_types import AsNoProxy
from amfast.remoting.flex_messages import CommandMessage
from amfast.remoting.channel import ChannelError

# --- CommandMessage Operations --- #
def client_ping(packet, msg, *args):
    """Respond to a ping request."""
    command = msg.body[0]
    response = msg.response_msg.body
    if (not hasattr(response, 'headers')) or response.headers is None:
        response.headers = {}

    response.headers[command.MESSAGING_VERSION] = 1
    response.headers[command.FLEX_CLIENT_ID_HEADER] = str(uuid.uuid4())

def subscribe_operation(packet, msg, *args):
    """Respond to a subscribe operation."""
    command = msg.body[0]

    # Set clientId
    # this ID is unique for each MessageAgent
    # acting as a consumer.
    ack_msg = msg.response_msg.body
    if ack_msg.clientId is None:
        ack_msg.clientId = str(uuid.uuid4())

    headers = command.headers
    channel = packet.channel_set.getChannel(headers[command.ENDPOINT_HEADER])

    connection = channel.getConnection(headers[command.FLEX_CLIENT_ID_HEADER])
    if connection is None:
        connection = channel.connect(headers[command.FLEX_CLIENT_ID_HEADER])

    packet.channel_set.message_agent.subscribe(connection, ack_msg.clientId,
        command.destination, headers.get(command.SUBTOPIC_HEADER, None),
        headers.get(command.SELECTOR_HEADER, None))

def unsubscribe_operation(packet, msg, *args):
    """Respond to a unsubscribe operation."""
    command = msg.body[0]
    headers = command.headers
    channel = packet.channel_set.getChannel(headers[command.ENDPOINT_HEADER])
    
    connection = channel.getConnection(headers[command.FLEX_CLIENT_ID_HEADER])
    if connection is not None:
        packet.channel_set.message_agent.unsubscribe(connection, command.clientId,
            command.destination, headers.get(command.SUBTOPIC_HEADER, None),
            headers.get(command.SELECTOR_HEADER, None))

def disconnect_operation(packet, msg, *args):
    """Respond to a disconnect operation."""
    command = msg.body[0]
    headers = command.headers

    connection = packet.channel_set.getConnection(headers[command.FLEX_CLIENT_ID_HEADER])
    if connection is not None:
        connection.channel.disconnect(headers[command.FLEX_CLIENT_ID_HEADER])

def poll_operation(packet, msg, *args):
    """Respond to a poll operation."""
    command = msg.body[0]
    headers = command.headers

    connection = packet.channel_set.getConnection(headers[command.FLEX_CLIENT_ID_HEADER])
    if connection is None:
        raise ChannelError("Client is not connected.")

    return AsNoProxy(connection.poll())
