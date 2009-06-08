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

class TimeOutError(ChannelError):
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

    NOTIFY_KEY = '_notify'

    def __init__(self, flex_client_id, channel):
        self.authenticated = False
        self.last_active = int(time.time())
        self.active = True

        self._lock = threading.RLock()
        self._flex_client_id = flex_client_id # Unique for each Flex client.
        self._channel = channel
        self._messages = []
        self._subscriptions = {}
        self._session_attrs = {}

        # Version 0.4 will use Beaker to store session data.
        # all 'new' attributes should be keyed to help compatibility
        # with upgrade to version 0.4.
        self.setSessionAttr(self.NOTIFY_KEY, False)

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
        return self._session_attrs[attr]

    def delSessionAttr(self, attr):
        """Remove a session attribute.

        arguments
        ==========
         * attr - string, name of attribute to remove.
        """
        self._lock.acquire()
        try:
            if attr in self._session_attrs:
                del self._session_attrs[attr]
        finally:
            self._lock.release()

    def setSessionAttr(self, attr, val):
        """Set a session attribute.

        arguments
        ==========
         * attr - string, name of attribute to set.
         * val - object, value to set.
        """
        self._session_attrs[attr] = val

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
        self._lock.acquire()
        try:
            for client_subscriptions in self._subscriptions.values():
                subscriptions.extend(client_subscriptions.values())
        finally:
            self._lock.release()

        return subscriptions

    def subscribe(self, client_id, topic):
        """Subscribe to a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to subscribe to.
        """
        subscription = Subscription(self, client_id, topic)

        self._lock.acquire()
        try:
            client_subscriptions = self._subscriptions.get(client_id, None)
            if client_subscriptions is None:
                client_subscriptions = {}
                self._subscriptions[client_id] = client_subscriptions
            client_subscriptions[topic] = subscription
        finally:
            self._lock.release()

        return subscription

    def unsubscribe(self, client_id, topic):
        """Un-Subscribe from a topic.

        arguments:
        ===========
         * client_id - string, MessageAgent clientId.
         * topic - string, the topic to un-subscribe from.
        """

        self._lock.acquire()
        try:
            client_subscriptions = self._subscriptions.get(client_id, None)
            if client_subscriptions is not None:
                if topic in client_subscriptions:
                    del client_subscriptions[topic]

                if len(client_subscriptions) < 1:
                    del self._subscriptions[client_id]
        finally:
            self._lock.release()

    def poll(self):
        """Returns all current messages and empties que."""
        results = self._messages
        self._messages = []

        return results

    def popMessage(self):
        """Remove and return a single message from the qeue."""
        return self._messages.pop()

    def hasMessages(self):
        """Returns True if messages are present."""
        return len(self._messages) > 0

    def publish(self, msg):
        """Add a message to the connection's message qeue.

        arguments
        ==========
         * msg, AbstractMessage, message to publish.
        """
        self._messages.append(msg)

        notify_func = self.getSessionAttr(self.NOTIFY_KEY)
        if notify_func is not False:
            # Notify that a message has been published
            notify_func()

    def clean(self, current_time=None):
        """Remove all expired messages."""
        if current_time is None:
            current_time = int(time.time())

        tmp = []
        self._lock.acquire()
        try:
             for msg in self._messages:
                 if msg.isExpired(current_time):
                     continue
                 tmp.append(msg)
             self._messages = tmp
        finally:
            self._lock.release()

class Channel(object):
    """An individual channel that can send/receive messages.

    attributes
    ===========
     * name - string, Channel name.
     * endpoint - Endpoint, encodes and decodes messages.
     * max_connections - int, When the number of connections exceeds this number,
         an exception is raised when new clients attempt to connect. Set to -1
         for no limit.
     * timeout - int, If a Connection's last_active value is < current time - timeout,
         the Connection will be disconnected.

    """

    def __init__(self, name, max_connections=-1, endpoint=None, timeout=1200):
        self.name = name
        self.max_connections = max_connections
        self.connection_count = 0
        self.timeout = timeout
        if endpoint is None:
            endpoint = AmfEndpoint()
        self.endpoint = endpoint
       
        self._lock = threading.RLock() 
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
        if self.max_connections > -1 and self.connection_count >= self.max_connections:
            raise ChannelError("Channel '%s' is not accepting connections." % self.name)

        try:
            self._channel_set.getConnection(flex_client_id)
        except NotConnectedError:
            pass
        else:
            raise ChannelError('Client ID is already connected.')
 
        self._lock.acquire()
        try:
            self.connection_count += 1
        finally:
            self._lock.release()

        connection = Connection(flex_client_id, self)
        self._channel_set.addConnection(connection)

        return connection

    def disconnect(self, connection):
        """Remove a client connection from this Channel.

        arguments
        ==========
         * flex_client_id - string, Flex client id.
        """
        self._lock.acquire()
        try:
            self.connection_count -= 1
        finally:
            self._lock.release()

        self.channel_set.disconnect(connection)

class HttpChannel(Channel):
    """An individual channel that can send/receive messages over HTTP.

    attributes
    ===========
     * wait_interval - int, Number of seconds to wait before sending response to client
         when a polling request is received. Set to -1 to configure channel as a
         long-polling channel.
    """

    # Content type for amf messages
    CONTENT_TYPE = 'application/x-amf'

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1800, wait_interval=0):

        Channel.__init__(self, name, max_connections, endpoint, timeout)

        self.wait_interval = wait_interval

    def waitForMessage(self, packet, message, connection):
        """Waits for a new message.

        This is blocking, and should only be used
        for Channels where each connection is a thread.
        """
        event = threading.Event()
        connection.setSessionAttr(connection.NOTIFY_KEY, event.set)
        if (self.wait_interval > -1):
            event.wait(self.wait_interval)

        # Event.set has been called,
        # or timeout has been reached
        connection.setSessionAttr(connection.NOTIFY_KEY, False)

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

        self._lock = threading.RLock()
        self._channels = {}
        self._connections = {}
        self.clean_freq = clean_freq
        self._last_cleaned = int(time.time())

    def __iter__(self):
        # To make thread safe
        channel_vals = self._channels.values()
        return channel_vals.__iter__

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
        self._connections[connection.flex_client_id] = connection

    def getConnection(self, flex_client_id):
        """Retrieve an existing connection.

        arugments
        ==========
         * flex_client_id - string, id of client to get connection for.
        """
        current_time = int(time.time())

        self._lock.acquire()
        try:
            connection = self._connections.get(flex_client_id, None)

            if connection is None:
                raise NotConnectedError('Client is not connected.')

            cutoff_time = current_time - connection.channel.timeout
            if connection.last_active < cutoff_time:
                raise TimeOutError('Connection is timed out.')
            
            connection.touch()
        except TimeOutError:
            connection.disconnect()
            raise NotConnectedError('Client is not connected.')
        finally:
            self._lock.release()

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
        subscriptions = connection.getSubscriptions()

        # Delete any subscriptions
        for subscription in subscriptions:
           self.message_agent.unsubscribe(subscription.connection,
               subscription.client_id, subscription.topic, _disconnect=True)

        self._lock.acquire()
        try:
            if connection.flex_client_id in self._connections:
                del self._connections[connection.flex_client_id]
        finally:
            self._lock.release()

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
        self._lock.acquire()
        try:
            self._channels[channel.name] = channel
            channel._channel_set = self
        finally:
            self._lock.release()

    def unMapChannel(self, channel):
        """Removes a Channel to the ChannelSet

        arguments
        ==========
         * channel - Channel, the channel to remove.
        """
        self._lock.acquire()
        try:
            if channel.name in self._channels:
                channel._channel_set = None
                del self._channels[channel.name]
        finally:
            self._lock.release()

    def getChannel(self, name):
        """Retrieves a Channel from the ChannelSet

        arguments
        ==========
         * name - string, the name of the Channel to retrieve.
        """
        return self._channels[name]

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
                self.disconnect(connection)
            else:
                connection.clean(current_time)
