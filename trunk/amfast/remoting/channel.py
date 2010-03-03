"""Send and receive AMF messages."""
import time
import threading
import uuid

import amfast
from amfast.class_def import ClassDefMapper

import connection_manager as cm
import subscription_manager as sm
import flex_messages as messaging
import thread_pool

class ChannelError(amfast.AmFastError):
    pass

class SecurityError(ChannelError):
    pass

class ChannelFullError(ChannelError):
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
            from endpoint import AmfEndpoint
            endpoint = AmfEndpoint()
        self.endpoint = endpoint
       
        self._lock = amfast.mutex_cls() 
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
            # Not much we can do if packet is not encoded properly
            amfast.log_exc(exc)
            raise exc

    def decode(self, *args, **kwargs):
        """Decode a raw request."""
        try:
            return self.endpoint.decodePacket(*args, **kwargs)
        except amfast.AmFastError, exc:
            # Not much we can do if packet is not decoded properly
            amfast.log_exc(exc)
            raise exc

    def invoke(self, request):
        """Invoke an incoming request packet."""
        try:
            request.channel = self # so user can access channel object
            return request.invoke()
        except amfast.AmFastError, exc:
            return request.fail(exc)

    def getFlexConnection(self, flex_msg):
        """Returns a Connection object for a Flex message.

        Creates a new Connection if one does not already exist.

        arguments
        ==========
         * flex_msg - FlexMessage object.
        """
        # If header does not exist, connection does not exist.
        if not hasattr(flex_msg, 'headers') or flex_msg.headers is None:
            return self.connect()

        flex_client_id = flex_msg.headers.get(flex_msg.FLEX_CLIENT_ID_HEADER, None)
        if flex_client_id == 'nil' or flex_client_id is None:
            return self.connect()

        try:
            return self.channel_set.connection_manager.getConnection(flex_msg.headers[flex_msg.FLEX_CLIENT_ID_HEADER])
        except cm.NotConnectedError:
            return self.connect(flex_msg.headers[flex_msg.FLEX_CLIENT_ID_HEADER])

    def connect(self, connection_id=None):
        """Add a client connection to this channel.

        arguments
        ==========
         * flex_client_id - string, Flex client id.

        Returns Connection
        """
        if self.max_connections > -1 and \
            self.channel_set.connection_manager.getConnectionCount(self.name) \
            >= self.max_connections:
            raise ChannelFullError("Channel '%s' is not accepting connections." % self.name)

        return self.channel_set.connect(self, connection_id)

    def disconnect(self, connection):
        """Remove a client connection from this Channel.

        arguments
        ==========
         * connection - Connection.
        """

        self.channel_set.disconnect(connection)

class HttpChannel(Channel):
    """An individual channel that can send/receive messages over HTTP.

    attributes
    ===========
     * wait_interval - int, Number of millisecondsseconds to wait before sending
         response to client when a polling request is received. Set to -1 to
         configure channel as a long-polling channel. Default = 0
     * poll_interval - int, Number of milliseconds between message polling operations
         when channel_set.notify == False
    """

    # Content type for amf messages
    CONTENT_TYPE = 'application/x-amf'

    def __init__(self, name, max_connections=-1, endpoint=None,
        wait_interval=0, poll_interval=500):

        Channel.__init__(self, name, max_connections, endpoint)

        self.wait_interval = wait_interval
        self.poll_interval = poll_interval

    def getBadMethodMsg(self):
        return "405 Method Not Allowed\n\nAMF request must use 'POST' method."

    def getBadEncodingMsg(self):
        return self.getBadRequestMsg('AMF packet could not be decoded.')

    def getBadRequestMsg(self, msg=''):
        return "400 Bad Request\n\n%s" % msg

    def getBadPageMsg(self, msg=''):
        return "404 Not Found\n\n%s" % msg

    def getBadServerMsg(self, msg=''):
        return "500 Internal Server Error\n\nAmFast server error.%s" % msg

    def waitForMessage(self, packet, message, connection):
        """Waits until a new message is published to this connection.
        Returns list of messages.
        """

        if self.channel_set.notify_connections is True:
            return self._waitForMessage(packet, message, connection)
        else:
            return self._pollForMessage(packet, message, connection)

    def _waitForMessage(self, packet, message, connection):
        """Waits until notified that a new message is available, then returns messages.

        This is blocking, and should only be used
        for Channels where each connection is a thread.

        Synchronous servers should override this method.
        """

        event = threading.Event()
        connection.setNotifyFunc(event.set)
        
        if (self.wait_interval > -1):
            event.wait(float(self.wait_interval) / 1000)

        # Event.set has been called,
        # or timeout has been reached.
        connection.unSetNotifyFunc()

        return self.channel_set.subscription_manager.pollConnection(connection)

    def _pollForMessage(self, packet, message, connection):
        """Repeatedly polls for a new message until
        message is available or wait_interval is reached.

        This is blocking, and should only be used
        for Channels where each connection is a thread.

        Synchronous servers should override this method.
        """
        # If True, don't store persistent 'last_polled' value every poll operation.
        soft_touch = hasattr(self.channel_set.connection_manager, "softTouchPolled")

        total_time = 0
        poll_secs = float(self.poll_interval) / 1000
        wait_secs = float(self.wait_interval) / 1000
        while True:
            event = threading.Event()
            event.wait(poll_secs)
            msgs = self.channel_set.subscription_manager.pollConnection(connection, soft_touch)
            if len(msgs) > 0:
                if soft_touch is True:
                    # Store 'last_polled' value.
                    connection.touchPolled()            
                return msgs
            
            total_time += poll_secs
            if total_time > wait_secs or connection.connected is False:
                if soft_touch is True:
                    # Store 'last_polled' value.
                    connection.touchPolled()
                return ()

class ChannelSet(object):
    """A collection of Channels.

    A client can access the same RPC exposed methods
    from any of the Channels contained in a ChannelSet.

    A Channel can only belong to 1 ChannelSet.

    attributes
    ===========
     * service_mapper - ServiceMapper, maps destinations to Targets.
     * connection_manager - ConnectionManager, keeps track of connected clients.
     * subscription_manager - SubscriptionManager, keeps track of subscribed clients.
     * notify_connections - boolean, set to True when using long-polling or streaming channels.
     * clean_freq - float - number of seconds to clean expired connections.
    """

    def __init__(self, service_mapper=None, connection_manager=None,
        subscription_manager=None, notify_connections=False, clean_freq=300):
        if service_mapper is None:
            from amfast.remoting import ServiceMapper
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        if connection_manager is None:
            connection_manager = cm.MemoryConnectionManager()
        self.connection_manager = connection_manager

        if subscription_manager is None:
            subscription_manager = sm.MemorySubscriptionManager()
        self.subscription_manager = subscription_manager

        self.notify_connections = notify_connections
        self.clean_freq = clean_freq
        self._lock = amfast.mutex_cls()
        self._channels = {}
        self.scheduleClean()

    def __iter__(self):
        # To make thread safe
        channel_vals = self._channels.values()
        return channel_vals.__iter__()

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

    def connect(self, channel, connection_id=None):
        """Add a client connection to this channel.

        arguments
        ==========
         * connection_id - string, Client connection id.

        Returns Connection
        """

        try:
            connection = self.connection_manager.getConnection(connection_id)
        except cm.NotConnectedError:
            pass
        else:
            raise ChannelError("Connection ID '%s' is already connected." % connection_id)

        return self.connection_manager.createConnection(channel, connection_id)

    def disconnect(self, connection):
        """Remove a client connection from this ChannelSet.

        arugments
        ==========
         * connection - Connection being disconnected.
        """

        self.subscription_manager.deleteConnection(connection)
        self.connection_manager.deleteConnection(connection)

    def scheduleClean(self):
        """Schedule connection cleaning procedure to run sometime in the future."""

        if amfast.use_dummy_threading is True:
            amfast.logger.warn('Connection cleaning was NOT scheduled.')
            return

        thread = threading.Timer(self.clean_freq, None)
        thread.daemon = True
        def _clean():
            self.clean()
            thread.start()
        thread.function = _clean
        thread.start()

    def clean(self):
        """Clean out expired connections."""
        if amfast.log_debug is True:
            amfast.logger.debug("Cleaning channel.")

        current_time = time.time() * 1000
        for connection_id in self.connection_manager.iterConnectionIds():
            self.cleanConnection(connection_id, current_time)

        if hasattr(self.subscription_manager, 'deleteExpiredMessages'):
            # TODO: better interface for deleting expired messages.
            #
            # Perhaps iterate through messages and delete expired
            # similar to how connection cleaning works??
            #
            # Currently, some subscriptions managers auto-delete
            # expired messages, while others require a method to be called.
            self.subscription_manager.deleteExpiredMessages(current_time)

    def cleanConnection(self, connection_id, current_time): 
        if amfast.log_debug is True: 
            amfast.logger.debug("Cleaning connection: %s" % connection_id) 
 
        try: 
            connection = self.connection_manager.getConnection(connection_id, False) 
        except cm.NotConnectedError:
            return
 
        if connection.last_active + connection.timeout < current_time: 
            channel = self.getChannel(connection.channel_name) 
            channel.disconnect(connection) 

    def publishObject(self, body, topic, sub_topic=None, headers=None, ttl=10000):
        """Create a message and publish it.

        arguments:
        ===========
        body - Any Python object.
        topic - string, the topic to publish to.
        sub_topic - string, the sub topic to publish to. Default = None
        headers - dict, headers to include with this message.
        ttl - int time to live in milliseconds. Default = 30000
        """

        if sub_topic is not None:
            if headers is None:
                headers = {}
            headers[messaging.AsyncMessage.SUBTOPIC_HEADER] = sub_topic

        current_time = time.time() * 1000

        msg = messaging.AsyncMessage(headers=headers, body=body,
            clientId=None, destination=topic, timestamp=current_time,
            timeToLive=ttl)
       
        self.publishMessage(msg)

    def publishMessage(self, msg):
        """Publish a pre-formed message.

        arguments:
        ===========
         * msg - AbstractMessage, the Flex message to publish.
        """

        self.subscription_manager.publishMessage(msg)

        if self.notify_connections is True:
            topic = msg.destination
            if hasattr(msg, 'headers') and \
                msg.headers is not None and \
                messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
                sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
            else:
                sub_topic = None

            self.notifyConnections(topic, sub_topic)

    def notifyConnections(self, topic, sub_topic):
        """Notify connections that a message has been published.

        arguments:
        ===========
         * topic - string, topic to notify
         * sub_topic - string, sub_topic to notify
        """
       
        thread_pool.GlobalThreadPool().addTask(self._notifyConnections, args=(topic, sub_topic)) 

    def _notifyConnections(self, topic, sub_topic):
        """Do the real work of notifyConnections."""

        for connection_id in self.subscription_manager.iterSubscribers(topic, sub_topic):
            try:
                connection = self.connection_manager.getConnection(connection_id, False)
            except cm.NotConnectedError:
                continue

            if connection.notify_func is not None:
                connection.notify_func()

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
        try:
            return self._channels[name]
        except KeyError:
            raise ChannelError("Channel '%s' is not mapped." % name)
