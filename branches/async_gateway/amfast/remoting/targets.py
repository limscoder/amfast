"""Built in Target functions."""

import uuid

def client_ping(packet, msg, *args):
    """Respond to a ping request."""
    response = msg.response_msg.value
    if response.headers is None:
        response.headers = {}

    response.headers['DSMessagingVersion'] = 1
    response.headers['DSId'] = str(uuid.uuid4())
    
    return True
