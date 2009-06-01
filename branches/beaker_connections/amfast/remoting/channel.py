"""Send and receive AMF messages."""
import time
import threading
import uuid

import amfast
from amfast.class_def import ClassDefMapper
from amfast.remoting.connection import Connection
from amfast.remoting.endpoint import AmfEndpoint

class ChannelError(amfast.AmFastError):
    pass

class NotConnectedError(ChannelError):
    pass

class SecurityError(ChannelError):
    pass

class Channel(object):
    """An individual channel that can send/receive messages.

    attributes
    ===========
     * name - string, Channel name.
     * endpoint - Endpoint, encodes and decodes messages.
     * max_connections - int, When the number of connections exceeds this number,
         an exception is raised when new clients attempt to connect. Set to -1
         for no limit.
    """

    def __init__(self, name, max_connections=-1, endpoint=None):
        self.name = name
        self.max_connections = max_connections
        self.connection_count = 0
        if endpoint is None:
            endpoint = AmfEndpoint()
        self.endpoint = endpoint
        
        self._channel_set = None

    def _getChannelSet(self):
        # Channel_set is read-only
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

    def connect(self, client_id):
        """Add a client connection to this channel.

        arguments
        ==========
         * client_id - string, client id.

        Returns Connection
        """
        if self.max_connections > -1 and self.connection_count >= self.max_connections:
            raise ChannelError("Channel '%s' is not accepting connections." % self.name)

        connection = self.channel_set.getConnection(client_id)
        connection[connection.CHANNEL_KEY] = self.name
        connection[connection.ACTIVE_KEY] = True
        connection[connection.MESSAGE_KEY] = []
        connection.save()

        lock = threading.RLock()
        lock.acquire()
        try:
            self.connection_count += 1
        finally:
            lock.release()

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
        wait_interval=0, check_interval=0.1):

        Channel.__init__(self, name, max_connections, endpoint)

        self._wait_interval = wait_interval
        self.check_interval = check_interval

    def _getWaitInterval(self):
        # Wait interval is read-only
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

    connection attributes
    ======================
     * timeout - int, Number of seconds that Connection objects should live for.
     * storage_type - string, The storage media to use for storing connection details.
         See Beaker docs for more info.
     * data_dir - string, Location to store connection files if 'type' == 'file'.
     * namespace_class - class, see Beaker docs.
     * namespace_args - dict, see Beaker docs.
    """

    def __init__(self, service_mapper=None, message_agent=None, clean_freq=300,
        timeout=1800, storage_type='memory', data_dir=None, namespace_class=None,
        namespace_args=None):
        if service_mapper is None:
            from amfast.remoting import ServiceMapper
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        if message_agent is None:
            from amfast.remoting.message_agent import MessageAgent
            message_agent = MessageAgent()
        self.message_agent = message_agent

        self._channels = {}
        self.clean_freq = clean_freq
        self._last_cleaned = int(time.time())

        # Connection attributes
        self.timeout = timeout
        self.storage_type = storage_type
        self.data_dir = data_dir
        self.namespace_class = namespace_class

        if namespace_args is None:
            namespace_args = {}
        self.namespace_args = namespace_args

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

    def getConnection(self, client_id):
        """Retrieve an existing connection.

        arugments
        ==========
         * client_id - string, id of client to get connection for.
        """
        connection = Connection(client_id, type=self.storage_type, data_dir=self.data_dir,
            timeout=self.timeout, namespace_class=self.namespace_class,
            **self.namespace_args)

        # Update connection every time it is accessed
        #connection.save(accessed_only=True)

        print "Got connection: %s" % connection

        # Clean up dead connections and subscriptions
        # TODO: there's got to be a better way to do this
        # while remaining agnostic to serving framework.
        # connection.channel.channel_set.clean()

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
