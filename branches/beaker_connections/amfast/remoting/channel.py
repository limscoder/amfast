"""Send and receive AMF messages."""
import time
import threading
import uuid

from beaker.session import Session

import amfast
from amfast.class_def import ClassDefMapper
from amfast.remoting.connection import Connection
from amfast.remoting.endpoint import AmfEndpoint
from amfast.remoting import flex_messages as messaging

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
            # Not much we can do if packet is not encoded properly
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
            request.channel = self # so user can access channel object from Target
            return request.invoke()
        except amfast.AmFastError, exc:
            return request.fail(exc)

    def connect(self, client_id):
        """Add a client connection to this channel.

        arguments
        ==========
         * client_id - string, client id
             client_id must be unique to each Flash client (flex_client_id).

        Returns Connection
        """
        connection = self.channel_set.getConnection(client_id, new=True)
        connection[connection.CHANNEL_KEY] = self.name
        connection[connection.MESSAGE_KEY] = []
        connection.save()

        return connection

    def disconnect(self, connection):
        """Remove a client connection from this Channel.

        arguments
        ==========
         * connection - Connection, the connection to disconnect.
        """
        print "Disconnecting '%s' from channel." % connection.id
        connection.disconnect()

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
    and published messages from any of the Channels
    contained within a ChannelSet.

    A Channel can only belong to 1 ChannelSet.

    attributes
    ===========
     * name - string, the name of the ChannelSet, must be globally unique.
     * service_mapper - ServiceMapper, maps destinations to Targets.
     * clean_freq - int, number of seconds between inactive Connection/Message cleaning.

    connection attributes
    ======================
     * con_timeout - int, Number of seconds that Connection objects should live for.
     * con_storage_type - string, see Beaker docs.
     * con_data_dir - string, see Beaker docs.
     * con_namespace_class - class, see Beaker docs.
     * con_namespace_args - dict, see Beaker docs.

    """

    SUBTOPIC_SEPARATOR = "_;_"
    SUBSCRIPTION_KEY = '_subscriptions'
    CONNECTION_KEY = '_connections'
    CHANNEL_KEY = '_channels'
    CLEANED_KEY = '_last_cleaned'

    def __init__(self, service_mapper=None, clean_freq=10, name="channelSet",
        secure_messages=False, storage_type='memory', data_dir=None,
        namespace_class=None, namespace_args=None, con_timeout=20,
        con_storage_type='memory', con_data_dir=None,
        con_namespace_class=None, con_namespace_args=None):

        # register channel name with module
        # so it can be accessed globally.
        self.name = name
        set_channel_set(self)

        self.clean_freq = clean_freq
        self.secure_messages = secure_messages
        self._channels = {}

        if service_mapper is None:
            from amfast.remoting import ServiceMapper
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        # connection attributes
        self.con_timeout = con_timeout
        self.con_storage_type = con_storage_type
        self.con_data_dir = con_data_dir
        self.con_namespace_class = con_namespace_class

        if con_namespace_args is None:
            con_namespace_args = {}
        self.con_namespace_args = con_namespace_args

        # Setup persistent storage
        if namespace_args is None:
            namespace_args = {}

        self._persistent = Session({}, id=self.name, 
            invalidate_corrupt=False, use_cookies=False, type=storage_type,
            data_dir=data_dir, timeout=100000000, cookie_expires=False,
            cookie_domain=None, secret=None, secure=False,
            namespace_class=namespace_class, **namespace_args)

        if self._persistent.is_new:
            # Setup persistent attributes
            self._persistent[self.CLEANED_KEY] = time.time()
            self._persistent[self.SUBSCRIPTION_KEY] = {}
            self._persistent[self.CONNECTION_KEY] = {}
            self._persistent[self.CHANNEL_KEY] = {}
            self._persistent.save()

    def __iter__(self):
        """Iterate through Channel objects."""
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

    def getConnection(self, client_id, touch=True, new=False):
        """Retrieve an existing connection.

        arugments
        ==========
         * client_id - string, id of client to get connection for.
             client_id should be unique for each Flash client (flex_client_id).
         * new - boolean, If False, raise NotConnectedError if
             connection doesn't exist yet.
        """
        connection = Connection(client_id, type=self.con_storage_type,
            data_dir=self.con_data_dir, timeout=self.con_timeout,
            namespace_class=self.con_namespace_class, **self.con_namespace_args)

        print "Got connection: %s" % connection

        if touch is True:
            connection[connection.ACCESSED_KEY] = time.time()
            connection.save()

            # Clean up dead connections and subscriptions
            # TODO: there's got to be a better way to do this
            # while remaining agnostic to serving framework.
            self.clean()

        if connection.is_new and new is False:
            connection.delete()
            raise NotConnectedError("Client '%s' is not connected." % client_id)

        return connection

    def subscribe(self, connection, client_id, topic,
        sub_topic=None, selector=None):
        """Subscribe a client to a topic.

        arguments
        ==========
         * connection - Connection, Connection that is subscribing.
         * client_id - string, MessageAgent clientId.
         * topic - string, Topic to subscribe to.
         * sub_topic - string, Sub-Topic to subscribe to. Default = None.
        """

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        self._persistent.lock()
        try:
            self._persistent.load()
            subscriptions = self._persistent[self.SUBSCRIPTION_KEY]
            topic_map = subscriptions.get(topic, None)
            if topic_map is None:
                topic_map = {}
                subscriptions[topic] = topic_map

            subscription = connection.subscribe(client_id, topic)
            topic_map[client_id] = subscription
            self._persistent.save()
        finally:
            self._persistent.unlock()

    def unsubscribe(self, connection, client_id, topic,
        sub_topic=None, selector=None, _disconnect=False):
        """Un-Subscribe a client from a topic.

        arguments
        ==========
         * connection - Connection, Connection that is subscribing.
         * client_id - string, MessageAgent clientId.
         * topic - string, Topic to un-subscribe from.
         * sub_topic - string, Sub-Topic to un-subscribe from. Default = None.
        """

        if sub_topic is not None:
            topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))

        self._persistent.lock()
        try:
            self._persistent.load()
            subscriptions = self._persistent[self.SUBSCRIPTION_KEY]
            topic_map = subscriptions.get(topic, None)
            if topic_map is not None:
               if client_id in topic_map:
                   del topic_map[client_id]

               if len(topic_map) < 1:
                   del subscriptions[topic]
            self._persistent.save()
        finally:
            self._persistent.unlock()

    def iterSubscriptions(self, topic):
        """Iterate through all Subscription objects for a topic."""
        subscriptions = self._persistent[self.SUBSCRIPTION_KEY]
        topic_map = subscriptions.get(topic, [])
        return topic_map.itervalues()

    def iterConnections(self, touch=True):
        """Iterate through all Connection objects."""
        for connection_id in self._persistent[self.CONNECTION_KEY].keys():
            try:
                yield self.getConnection(connection_id, touch=touch)
            except NotConnectedError:
                continue

    def publish(self, body, topic, sub_topic=None, client_id=None, ttl=600):
        """Publish a message.

        arguments:
        ===========
        body - AbstractMessage or any Python object.
        topic - string, the topic to publish to.
        sub_topic - string, the sub topic to publish to. Default = None
        client_id - string, if provided, only publish to specific MessageAgent client. Default = None
        ttl - int time to live in secoded. Default = 600
        """

        current_time = int(time.time() * 1000)
        ttl *= 1000

        if sub_topic is not None:
            com_topic = self.SUBTOPIC_SEPARATOR.join((topic, sub_topic))
        else:
            com_topic = topic

        if client_id is not None:
            # TODO: publish to individual client!!
            #if client_id in self._clients:
            #    connections = {client_id: self._clients[client_id]}
            pass

        # Get msg properties
        if isinstance(body, messaging.AbstractMessage):
            msg_class = body.__class__
            headers = body.headers
            body = body.body
        else:
            msg_class = messaging.AsyncMessage
            headers = None

        if sub_topic is not None:
            if headers is None:
                headers = {}
            headers[messaging.AsyncMessage.SUBTOPIC_HEADER] = sub_topic

        # Create msg to publish
        msg = msg_class(headers=headers, body=body, timeToLive=ttl,
            destination=topic, timestamp=current_time)

        for subscription in self.iterSubscriptions(com_topic):
            try:
                connection = self.getConnection(subscription.connection_id, touch=False)
            except NotConnectedError:
                pass
            else:
                connection.publish(msg, subscription.client_id)

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

        # Check number of connections
        connection = self.connect(flex_client_id, packet.channel)

        response = msg.response_msg.body
        if (not hasattr(response, 'headers')) or response.headers is None:
            response.headers = {}
        response.headers[flex_msg.FLEX_CLIENT_ID_HEADER] = flex_client_id
        return connection

    def connect(self, client_id, channel):
        """Connect a client."""
        self._persistent.lock()
        try:
            self._persistent.load()
            if channel.max_connections > -1 \
                and self._persistent[self.CHANNEL_KEY][channel.name] >= channel.max_connections:
                raise ChannelError("Channel '%s' is not accepting connections." % channel.name)

            connection = channel.connect(client_id)

            self._persistent[self.CHANNEL_KEY][channel.name] += 1
            self._persistent[self.CONNECTION_KEY][connection.id] = True
            self._persistent.save()
        finally:
            self._persistent.unlock()

        return connection

    def disconnect(self, connection, channel):
        """Disconnect a client."""

        channel.disconnect(connection)

        self._persistent.lock()
        try:
            self._persistent.load()
            self._persistent[self.CHANNEL_KEY][channel.name] -= 1
            del self._persistent[self.CONNECTION_KEY][connection.id]
            self._persistent.save()
        finally:
            self._persistent.unlock()

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
            self._persistent[self.CHANNEL_KEY][channel.name] = 0
            self._persistent.save()
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

            if channel.name in self._persistent[self.CHANNEL_KEY]:
                del self._persistent[self.CHANNEL_KEY]
                self._persistent.save()
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

    def clean(self, force=False):
        """Remove inactive Connections and Messages.

        Spins a new thread to do the work, but only
        if the last clean() was performed before
        self.clean_freq.
        """
        print "Checking clean"
        current_time = time.time()
        cutoff = current_time - self.clean_freq
        if force is True or self._persistent[self.CLEANED_KEY] < cutoff:
            self._persistent[self.CLEANED_KEY] = current_time
            self._persistent.save()
            t = threading.Timer(0, self._clean, (current_time,))
            t.start()

    def _clean(self, current_time):
        """Implementation for self.clean()."""
        print "!! ---- _cleaning ---- !!"
        channels = {}
        for connection in self.iterConnections(touch=False):
            print "checking connection: '%s'" % connection.id
            cutoff = current_time - connection.timeout
            if connection[connection.ACCESSED_KEY] < cutoff:
                print "Connection '%s' is timedout" % connection.id
                channel_name = connection[connection.CHANNEL_KEY]
                channel = channels.get(channel_name, None)
                if channel is None:
                    channel = self.getChannel(channel_name)
                    channels[channel_name] = channel
                self.disconnect(connection, channel)
            else:
                print "Connection '%s' is ready for message clean" % connection.id
                connection.clean(current_time)

# ---- Module attributes ---- #
_channel_sets = {}

def get_channel_set(name):
    """Get a ChannelSet by name."""
    return _channel_sets.get(name, None)

def set_channel_set(channel_set):
    """Store a ChannelSet by name."""
    if channel_set.name in _channel_sets:
        raise ChannelError("ChannelSet '%s' already exists." % channel_set.name)

    _channel_sets[channel_set.name] = channel_set
