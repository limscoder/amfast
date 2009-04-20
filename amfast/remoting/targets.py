"""Built in Target functions."""

import uuid

# --- CommandMessage Operations --- #
def client_ping(packet, msg, *args):
    """Respond to a ping request."""
    command = msg.body[0]
    response = msg.response_msg.body
    if response.headers is None:
        response.headers = {}

    response.headers[command.MESSAGING_VERSION] = 1
    response.headers[command.FLEX_CLIENT_ID_HEADER] = str(uuid.uuid4())

def subscribe_operation(packet, msg, *args):
    """Respond to a subscribe operation."""
    command = msg.body[0]
    headers = command.headers
    channel = packet.channel_set.getChannel(headers[command.ENDPOINT_HEADER])
    packet.channel_set.message_broker.subscribe(headers[command.FLEX_CLIENT_ID_HEADER],
        channel, command.destination, headers.get(command.SUBTOPIC_HEADER, None),
        headers.get(command.SELECTOR_HEADER, None))

def disconnect_operation(packet, msg, *args):
    """Respond to a disconnect operation."""
    command = msg.body[0]
    packet.channel_set.message_broker.disconnect(command.headers[command.FLEX_CLIENT_ID_HEADER])

def poll_operation(packet, msg, *args):
    """Respond to a poll operation."""
    command = msg.body[0]
    return packet.channel_set.message_broker.poll(command.headers[command.FLEX_CLIENT_ID_HEADER])
