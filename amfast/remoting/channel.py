"""Send and receive AMF messages."""
import time
import threading
import uuid

import amfast
from amfast.class_def import ClassDefMapper
from amfast.remoting.endpoint import AmfEndpoint

class ChannelError(amfast.AmFastError):
    pass

class NotConnectedError(ChannelError):
    pass

class SecurityError(ChannelError):
    pass

class Subscription(object):
    """An MessageAgent's subscription to a topic.

    attributes
    ===========
     * connection - Connection, the connection the Subscription belongs to.
     * client_id - string, the MessageAgent's clientId.
     * topic - string, the name of the topic subscribed to. The
         topic string also contains the sub-topic.
    """

    def __init__(self, connection, client_id, topic):
        self.connection = connection
        self.client_id = client_id # Unique for each MessageAgent
        self.topic = topic

class Connection(object):
    """A client connection to a Channel.
    This class acts like a session.
    Unique to a Flex client.

    attributes
    ===========
     * channel - Channel, read-only, The Channel this connection uses.
     * flex_client_id - string, read-only, The Flex client id is unique to a Flex client.
     * last_active - int, epoch time when Connection was last accessed.
     * authenticated - boolean, True if Connection has been authenticated.
     * active - boolean, True if Connection is in use
    """

    def __init__(self, flex_client_id, channel):
        self.authenticated = False
        self.last_active = int(time.time())
        self.active = True
        self.connected = False

        self._flex_client_id = flex_client_id # Unique for each Flex client.
        self._channel = channel
        self._messages = []
        self._subscriptions = {}
        self._session_attrs = {}

    # channel should be read only
    def _getChannel(self):
        return self._channel
    channel = property(_getChannel)

    # flex_client_id should be read only
    def _getFlexClientId(self):
        return self._flex_client_id
    flex_client_id = property(_getFlexClientId)

    def hasSessionAttr(self, attr):
        """Returns True if session attribute is present.

        arguments
        ==========
         * attr - string, name of the attribute to query.
        """
        return attr in self._session_attrs

    def getSessionAttr(self, attr):
        """Get the value of a session attribute.
 
        arguments
        ==========
         * attr - string, name of attribute to retrieve.
        """
        lock = threading.RLock()
        lock.acquire()
        try:
            return self._session_attrs[attr]
        finally:
            lock.release()

    def delSessionAttr(self, attr):
        """Remove a session attribute.

        arguments
        ==========
         * attr - string, name of attribute to remove.
        """

        lock = threading.RLock()
        lock.acquire()
        try:
            if attr in self._session_attrs:
                del self._session_attrs[attr]
        finally:
            lock.release()

    def setSessionAttr(self, attr, val):
        """Set a session attribute.

        arguments
        ==========
         * attr - string, name of attribute to set.
         * val - object, value to set.
        """

        lock = threading.RLock()
        lock.acquire()
        try:
            self._session_attrs[attr] = val
        finally:
            lock.release()

    def touch(self):
         """Updates last_active to the current time."""
         self.last_active = int(time.time())

    def disconnect(self):
        """Disconnects this connection."""
        self.active = False
        self.channel.disconnect(self)

    def getSubscriptions(self):
        """Returns a list of subscription objects."""
        subscriptions = []

        # Is there a way to make a thread-safe
        # generator for this? ...don't think so.
        lock = threading.RLock()
        lock.acquire()
        try:
            for client_subscriptions in self._subscriptions.values():
                subscriptions.extend(client_subscriptions.values())
        finally:
            lock.release()

        return subscriptions

    def subscribe(self, client_id, topic):
        """Subscribe to a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to subscribe to.
        """
        subscription = Subscription(self, client_id, topic)

        lock = threading.RLock()
        lock.acquire()
        try:
            client_subscriptions = self._subscriptions.get(client_id, None)
            if client_subscriptions is None:
                client_subscriptions = {}
                self._subscriptions[client_id] = client_subscriptions
            client_subscriptions[topic] = subscription
        finally:
            lock.release()

        return subscription

    def unsubscribe(self, client_id, topic):
        """Un-Subscribe from a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to un-subscribe from.
        """

        lock = threading.RLock()
        lock.acquire()
        try:
            client_subscriptions = self._subscriptions.get(client_id, None)
            if client_subscriptions is not None:
                if topic in client_subscriptions:
                    del client_subscriptions[topic]
        finally:
            lock.release()

    def poll(self):
        """Returns all current messages and empties que."""
        results = self._messages
        self._messages = []

        return results

    def popMessage(self):
        """Remove and return a single message from the qeue."""
        lock = threading.RLock()
        lock.acquire()
        try:
            return self._messages.pop(0)
        finally:
            lock.release()

    def hasMessages(self):
        """Returns True if messages are present."""
        return len(self._messages) > 0

    def publish(self, msg):
        """Add a message to the connection's message qeue.

        arguments
        ==========
         * msg, AbstractMessage, message to publish.
        """
        lock = threading.RLock()
        lock.acquire()
        try:
            self._messages.append(msg)
        finally:
            lock.release()

    def clean(self, current_time=None):
        """Remove all expired messages."""
        if current_time is None:
            current_time = int(time.time())

        tmp = []
        lock = threading.RLock()
        lock.acquire()
        try:
             for msg in self._messages:
                 if msg.isExpired(current_time):
                     continue
                 tmp.append(msg)
             self._messages = tmp
        finally:
            lock.release()

class StreamingConnection(Connection):
    """Publish messages directly to stream, instead of to the qeue.

     attributes
     ===========
     * connected - boolean, True if Connection is connected and streaming
     * heart_interval - int, Number of seconds between heart beat responses.
     * channel_publish - bool, True if self.publish should be called.
     """
    def __init__(self, flex_client_id, channel,
        channel_publish=True, connected=False,
        heart_interval=30):

        Connection.__init__(self, flex_client_id, channel)
        self.connected = connected
        self.heart_interval = heart_interval
        self.channel_publish = channel_publish

    def publish(self, msg):
        self.touch() # I touch myself, but only when no one is looking to make sure my connection stays alive
        if self.channel_publish is True and self.connected is True:
            self.channel.publish(self, msg)
        else:
            Connection.publish(self, msg)

class Channel(object):
    """An individual channel that can send/receive messages.

    attributes
    ===========
     * name - string, Channel name.
     * endpoint - Endpoint, encodes and decodes messages.
     * max_connections - int, When the number of connections exceeds this number,
         an exception is raised when new clients attempt to connect. Set to -1
         for no limit.
     * connection_class - Connection, The class to use for new connections.
     * timeout - int, If a Connection's last_active value is < current time - timeout,
         the Connection will be disconnected.

    """

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1800, connection_class=Connection):
        self.name = name
        self.max_connections = max_connections
        self.connection_class = connection_class
        self.timeout = timeout
        if endpoint is None:
            endpoint = AmfEndpoint()
        self.endpoint = endpoint
        
        self._channel_set = None

    def _getChannelSet(self):
        # channel_set should be considered
        # read-only outside of this class
        return self._channel_set
    channel_set = property(_getChannelSet)

    def encode(self, *args, **kwargs):
        """Encode a packet."""
        try:
            return self.endpoint.encodePacket(*args, **kwargs)
        except amfast.AmFastError, exc:
            # Not much we can do if packet is not decoded properly
            amfast.log_exc()
            raise exc

    def decode(self, *args, **kwargs):
        """Decode a raw request."""
        try:
            return self.endpoint.decodePacket(*args, **kwargs)
        except amfast.AmFastError, exc:
            # Not much we can do if packet is not decoded properly
            amfast.log_exc()
            raise exc

    def invoke(self, request):
        """Invoke an incoming request packet."""
        try:
            request.channel = self # so user can access channel object
            return request.invoke()
        except amfast.AmFastError, exc:
            return request.fail(exc)

    def connect(self, flex_client_id):
        """Add a client connection to this channel.

        arguments
        ==========
         * flex_client_id - string, Flex client id.

        Returns Connection
        """
        if self.max_connections > -1 and len(self._connections) >= self.max_connections:
            raise ChannelError("Channel '%s' is not accepting connections." % self.name)

        connection = self.connection_class(flex_client_id, self)
        self._channel_set.addConnection(self.connection_class(flex_client_id, self))

        return connection

    def disconnect(self, connection):
        """Remove a client connection from this Channel.

        arguments
        ==========
         * flex_client_id - string, Flex client id.
        """
        self.channel_set.disconnect(connection)

class HttpChannel(Channel):
    """An individual channel that can send/receive messages over HTTP.

    attributes
    ===========
     * wait_interval - int, Number of seconds to wait before sending response to client
         when a polling request is received. Set to -1 to configure channel as a
         long-polling channel.
     * check_interval - int or float, Number of seconds to wait between message
         qeue checks when checking for new messages. Internal polling interval.
    """

    # Content type for amf messages
    CONTENT_TYPE = 'application/x-amf'

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1800, connection_class=Connection, wait_interval=0,
        check_interval=0.1):

        Channel.__init__(self, name, max_connections, endpoint,
            timeout, connection_class)

        self._wait_interval = wait_interval
        self.check_interval = check_interval

    # wait_interval should be read-only
    def _getWaitInterval(self):
        return self._wait_interval
    wait_interval = property(_getWaitInterval)

    def waitForMessage(self, packet, message, connection):
        """Waits for a new message.

        This is blocking, and should only be used
        for Channels where each connection is a thread.
        """
        total = 0
        while True:
            if connection.active is False:
                return

            if connection.hasMessages():
                return

            if self.wait_interval > 0 and total > self.wait_interval:
                # Max wait interval reached.
                return

            time.sleep(self.check_interval)
            total += self.check_interval

class ChannelSet(object):
    """A collection of Channels.

    A client can access the same RPC exposed methods
    from any of the Channels contained in a ChannelSet.

    A Channel can only belong to 1 ChannelSet.

    attributes
    ===========
     * service_mapper - ServiceMapper, maps destinations to Targets.
     * message_agent - MessageAgent, handles Producer/Consumer messages.
     * clean_freq - int, number of seconds between inactive Connection/Message cleaning.
    """

    def __init__(self, service_mapper=None, message_agent=None, clean_freq=300):
        if service_mapper is None:
            from amfast.remoting import ServiceMapper
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        if message_agent is None:
            from amfast.remoting.message_agent import MessageAgent
            message_agent = MessageAgent()
        self.message_agent = message_agent

        self._channels = {}
        self._connections = {}
        self.clean_freq = clean_freq
        self._last_cleaned = int(time.time())

    def __iter__(self):
        return self._channels.itervalues()

    def checkCredentials(self, user, password):
        """Determines if credentials are valid.

        arguments
        ==========
         * user - string, username.
         * password - string, password.

        Returns True if credentials are valid.
        Raises SecurityError if credentials are invalid.
        """
        raise SecurityError('Authentication not implemented.');

    def generateId(self):
        """Generates a unique ID for Flex clients or MessageAgent clients.

        Returns string.
        """
        return str(uuid.uuid4())

    def addConnection(self, connection):
        """Add a connection to the ChannelSet."""
        lock = threading.RLock()
        lock.acquire()
        try:
            self._connections[connection.flex_client_id] = connection
        finally:
            lock.release()

    def getConnection(self, flex_client_id):
        """Retrieve an existing connection.

        arugments
        ==========
         * flex_client_id - string, id of client to get connection for.
        """
        current_time = int(time.time())

        lock = threading.RLock()
        lock.acquire()
        try:
            connection = self._connections.get(flex_client_id, None)

            if connection is None:
                raise NotConnectedError('Client is not connected.')

            cutoff_time = current_time - connection.channel.timeout
            if connection.last_active < cutoff_time:
                connection.disconnect()
                raise NotConnectedError('Client is not connected.')
            
            connection.touch()
        finally:
            lock.release()

        # Clean up dead connections and subscriptions
        # TODO: there's got to be a better way to do this
        # while remaining agnostic to serving framework.
        connection.channel.channel_set.clean()

        return connection

    def disconnect(self, connection):
        """Remove a client connection from this ChannelSet.

        arugments
        ==========
         * flex_client_id - string, id of client to get connection for.
        """
        lock = threading.RLock()
        lock.acquire()
        try:
           # Delete any subscriptions
           subscriptions = connection.getSubscriptions()
           for subscription in subscriptions:
               self.message_agent.unsubscribe(subscription.connection,
                   subscription.client_id, subscription.topic)

           if connection.flex_client_id in self._connections:
               del self._connections[connection.flex_client_id]
        finally:
            lock.release()

    def getFlexConnection(self, packet, msg):
        """Returns a Connection object for a Flex message.

        Creates a new Connection if one does not already exist.

        arguments
        ==========
         * packet - Packet, request Packet.
         * msg - Message, request Message.
        """
        flex_msg = msg.body[0]
        try:
            # If header does not exist,
            # connection does not exist.
            if not hasattr(flex_msg, 'headers') or flex_msg.headers is None:
                return self.flexConnect(packet, msg)

            flex_client_id = flex_msg.headers.get(flex_msg.FLEX_CLIENT_ID_HEADER, None)
            if flex_client_id == 'nil' or flex_client_id is None:
                return self.flexConnect(packet, msg)

            return self.getConnection(flex_msg.headers[flex_msg.FLEX_CLIENT_ID_HEADER])
        except NotConnectedError:
            return self.flexConnect(packet, msg)

    def flexConnect(self, packet, msg):
        """Creates a new Connection object and returns it.

        arguments
        ==========
         * packet - Packet, request Packet.
         * msg - Message, request Message.
        """
        flex_msg = msg.body[0]

        if not hasattr(flex_msg, 'headers') or flex_msg.headers is None:
            flex_msg.headers = {}

        flex_client_id = flex_msg.headers.get(flex_msg.FLEX_CLIENT_ID_HEADER, None)
        if flex_client_id == 'nil' or flex_client_id is None:
            flex_client_id = self.generateId()
 
        connection = packet.channel.connect(flex_client_id)

        response = msg.response_msg.body
        if (not hasattr(response, 'headers')) or response.headers is None:
            response.headers = {}
        response.headers[flex_msg.FLEX_CLIENT_ID_HEADER] = flex_client_id
        return connection

    def mapChannel(self, channel):
        """Add a Channel to the ChannelSet

        arguments
        ==========
         * channel - Channel, the channel to add.
        """
        lock = threading.RLock()
        lock.acquire()
        try:
            self._channels[channel.name] = channel
            channel._channel_set = self
        finally:
            lock.release()

    def unMapChannel(self, channel):
        """Removes a Channel to the ChannelSet

        arguments
        ==========
         * channel - Channel, the channel to remove.
        """
        lock = threading.RLock()
        lock.acquire()
        try:
            if channel.name in self._channels:
                channel._channel_set = None
                del self._channels[channel.name]
        finally:
            lock.release()

    def getChannel(self, name):
        """Retrieves a Channel from the ChannelSet

        arguments
        ==========
         * name - string, the name of the Channel to retrieve.
        """

        lock = threading.RLock()
        lock.acquire()
        try:
            channel = self._channels[name]
        finally:
            lock.release()
        return channel

    def clean(self):
        """Remove inactive Connections and Messages.

        Spins a new thread to do the work, but only
        if the last clean() was performed before
        self.clean_freq.
        """
        current_time = int(time.time())
        cutoff = current_time - self.clean_freq
        if self._last_cleaned < cutoff:
            self._last_cleaned = current_time
            t = threading.Timer(0, self._clean, (current_time,))
            t.start()

    def _clean(self, current_time):
        """Implementation for self.clean()."""
        for connection in self._connections.values():
            cutoff = current_time - connection.channel.timeout
            if connection.last_active < cutoff:
                self.disconnect(connection.flex_client_id)
            else:
                connection.clean(current_time)
