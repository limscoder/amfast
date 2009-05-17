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

# --- CommandMessage Operations --- #

def client_ping(packet, msg, *args):
    """Respond to a ping request and connect to the Channel."""
    response = msg.response_msg.body
    if (not hasattr(response, 'headers')) or response.headers is None:
        response.headers = {}

    # Set FlexClientId (unique to a single Flex client)
    # and create connection.
    connection = packet.channel.channel_set.getFlexConnection(packet, msg)

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
    connection = channel_set.getFlexConnection(packet, msg)
    connection.authenticated = True
    connection.setSessionAttr('flex_user', creds[0])

def logout_operation(packet, msg, *args):
    """RemoteObject style de-authentication."""

    connection = packet.channel.channel_set.getFlexConnection(packet, msg)
    connection.authenticated = False
    connection.delSessionAttr('flex_user')

def subscribe_operation(packet, msg, *args):
    """Respond to a subscribe operation."""
    command = msg.body[0]
    headers = command.headers

    # Subscribe to topic
    channel_set = packet.channel.channel_set
    connection = channel_set.getFlexConnection(packet, msg)

    if channel_set.message_agent.secure is True:
        if connection.authenticated is False:
            raise SecurityError("Operation requires authentication.")

    channel_set.message_agent.subscribe(connection, command.clientId,
        command.destination, headers.get(command.SUBTOPIC_HEADER, None),
        headers.get(command.SELECTOR_HEADER, None))

def unsubscribe_operation(packet, msg, *args):
    """Respond to an unsubscribe operation."""
    command = msg.body[0]
    headers = command.headers
   
    channel_set = packet.channel.channel_set
    connection = channel_set.getFlexConnection(packet, msg)
    if connection is not None:
        channel_set.message_agent.unsubscribe(connection, command.clientId,
            command.destination, headers.get(command.SUBTOPIC_HEADER, None),
            headers.get(command.SELECTOR_HEADER, None))

def disconnect_operation(packet, msg, *args):
    """Respond to a disconnect operation. Disconnects current Connection."""
    command = msg.body[0]
    headers = command.headers

    connection = packet.channel.channel_set.getFlexConnection(packet, msg)
    connection.disconnect()
    response = msg.response_msg.body

    if hasattr(response, 'headers') and response.FLEX_CLIENT_ID_HEADER in response.headers:
        del response.headers[response.FLEX_CLIENT_ID_HEADER]

def poll_operation(packet, msg, *args):
    """Respond to a poll operation. Returns queued messages."""
    command = msg.body[0]
    headers = command.headers

    channel = packet.channel
    connection = channel.channel_set.getFlexConnection(packet, msg)

    if channel.wait_interval < 0:
        # Long polling channel, don't return response
        # until a message is available.
        if not connection.hasMessages():
            # Only wait for messages,
            # if message qeue is currently empty
            #
            # Let the channel handle the implementation,
            # because implementation will be different for
            # Async servers (Twisted) and threaded servers (everything else)
            channel.waitForMessage(packet, msg, connection)
    elif channel.wait_interval > 0:
        # TODO: make this non-blocking for async servers
        time.sleep(channel.wait_interval)
    messages = connection.poll()

    if isinstance(packet.channel.endpoint, AmfEndpoint):
        # Make sure messages are not encoded as an ArrayCollection
        return AsNoProxy(messages)
    else:
        return messages
