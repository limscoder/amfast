"""Built in Target functions."""

import uuid

# --- CommandMessage Operations --- #
def client_ping(packet, msg, *args):
    """Respond to a ping request."""
    response = msg.response_msg.body
    if response.headers is None:
        response.headers = {}

    response.headers['DSMessagingVersion'] = 1
    response.headers['DSId'] = str(uuid.uuid4())

def subscribe_operation(packet, msg, *args):
    """Respond to a subscribe operation."""
    command = msg.body[0]
    headers = command.headers
    channel = packet.channel_set.getChannel(headers['DSEndpoint'])
    packet.channel_set.message_broker.subscribe(headers['DSId'],
        channel, command.destination, headers.get('DSSubtopic', None),
        headers.get('DSSelector', None))

def disconnect_operation(packet, msg, *args):
    """Respond to a disconnect operation."""
    command = msg.body[0]
    packet.channel_set.message_broker.disconnect(command.headers['DSId'])

def poll_operation(packet, msg, *args):
    """Respond to a poll operation."""
    command = msg.body[0]
    return packet.channel_set.message_broker.poll(command.headers['DSId'])
