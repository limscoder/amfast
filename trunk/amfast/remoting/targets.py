"""Built in Target functions."""
import base64

from amfast.class_def.as_types import AsNoProxy
from amfast.remoting.flex_messages import CommandMessage
from amfast.remoting.channel import ChannelError, SecurityError
from amfast.remoting.endpoint import AmfEndpoint

# ---- NetConnection Operations --- #

def nc_auth(packet, msg, credentials):
    """NetConnection style authentication."""
    packet.channel.channel_set.checkCredentials(
        credentials['userid'], credentials['password'])

    # Flag indicating packet was 
    # authenticated properly.
    packet._authenticated = True

# --- Flex CommandMessage Operations --- #

def client_ping(packet, msg, *args):
    """Respond to a ping request and connect to the Channel."""

    response = msg.response_msg.body
    if (not hasattr(response, 'headers')) or response.headers is None:
        response.headers = {}

    command = msg.body[0]
    response.headers[command.FLEX_CLIENT_ID_HEADER] = command.connection.id

def login_operation(packet, msg, raw_creds):
    """RemoteObject style authentication."""

    cred_str = base64.decodestring(raw_creds)

    command = msg.body[0]
    if hasattr(command, 'headers') and \
        command.CREDENTIALS_CHARSET_HEADER in command.headers:
        # Convert encoded string
        cred_str = unicode(cred_str, command.headers[command.CREDENTIALS_CHARSET_HEADER])

    creds = cred_str.split(':')
    
    channel_set = packet.channel.channel_set
    channel_set.checkCredentials(creds[0], creds[1])
    command.connection.authenticate(creds[0])

def logout_operation(packet, msg, *args):
    """RemoteObject style de-authentication."""

    command = msg.body[0]
    command.connection.unAuthenticate()

def disconnect_operation(packet, msg, *args):
    """Respond to a disconnect operation. Disconnects current Connection."""

    command = msg.body[0]
    packet.channel.disconnect(command.connection)

    response = msg.response_msg.body
    if hasattr(response, 'headers') and response.FLEX_CLIENT_ID_HEADER in response.headers:
        del response.headers[response.FLEX_CLIENT_ID_HEADER]

def subscribe_operation(packet, msg, *args):
    """Respond to a subscribe operation."""
    command = msg.body[0]

    channel_set = packet.channel.channel_set
    if channel_set.subscription_manager.secure is True:
        if command.connection.authenticated is False:
            raise SecurityError("Operation requires authentication.")

    headers = command.headers
    channel_set.subscription_manager.subscribe(command.connection.id,
        command.clientId, command.destination,
        headers.get(command.SUBTOPIC_HEADER, None),
        headers.get(command.SELECTOR_HEADER, None))

def unsubscribe_operation(packet, msg, *args):
    """Respond to an unsubscribe operation."""
    command = msg.body[0]
    packet.channel.channel_set.subscription_manager.unSubscribe(
        command.connection.id, command.clientId, command.destination,
        command.headers.get(command.SUBTOPIC_HEADER, None))

def poll_operation(packet, msg, *args):
    """Respond to a poll operation. Returns queued messages."""
    command = msg.body[0]
    connection = command.connection
    channel = packet.channel

    msgs = channel.channel_set.subscription_manager.pollConnection(connection)
    if len(msgs) < 1 and channel.wait_interval != 0:
        # Long polling channel, don't return response
        # until a message is available.
        msgs = channel.waitForMessage(packet, msg, connection)

    if isinstance(channel.endpoint, AmfEndpoint):
        # Make sure messages are not encoded as an ArrayCollection
        return AsNoProxy(msgs)
    else:
        return msgs
