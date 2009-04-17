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
    
    return True

def subscribe_operation(packet, msg, *args):
    """Respond to a subscribe operation."""
    command = msg.body[0]
    headers = command.headers
    channel = packet.gateway.getChannelByName(headers['DSEndpoint'])
    packet.gateway.message_publisher.subscribe(headers['DSId'],
        channel, command.destination, headers.get('DSSubtopic', None),
        headers.get('DSSelector', None))

    return True
