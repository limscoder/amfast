"""Send and receive AMF messages."""
import time
import threading

import amfast
from amfast import AmFastError
from amfast.class_def import ClassDefMapper
from amfast.remoting import ServiceMapper, RemotingError
from amfast.remoting.endpoint import AmfEndpoint
from amfast.remoting.message_agent import MessageAgent, Subscription

class ChannelError(RemotingError):
    pass

class Connection(object):
    """A client connection to a channel."""

    def __init__(self, flex_client_id, channel):
        self.flex_client_id = flex_client_id # Unique for each Flex client.
        self.channel = channel
        
        self._last_active = int(time.time())
        self._messages = []
        self._subscriptions = {}

    def getSubscriptions(self):
        subscriptions = []

        lock = threading.RLock()
        lock.acquire()
        try:
            for client_subscriptions in self._subscriptions.values():
                subscriptions.extend(client_subscriptions.values())
        finally:
            lock.release()

        return subscriptions

    def subscribe(self, client_id, topic):
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
        lock = threading.RLock()
        lock.acquire()
        try:
             results = self._messages
             self._messages = []
             self._last_active = int(time.time())
        finally:
            lock.release()

        return results

    def publish(self, msg):
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

class Channel(object):
    """An individual channel that can be send/recieve messages."""

    CONTENT_TYPE = 'application/x-amf'

    def __init__(self, name, max_connections=-1, endpoint=None,
        time_to_live=1800, clean_freq=300, connection_class=Connection):
        self.name = name
        self.max_connections = max_connections
        self.connection_class = connection_class
        self.time_to_live = time_to_live
        self.clean_freq = clean_freq
        self._last_cleaned = int(time.time())

        if endpoint is None:
            endpoint = AmfEndpoint()
        self.endpoint = endpoint
        
        self._connections = {}
        self._channel_set = None

    def _getChannelSet(self):
        # channel_set should be considered
        # read-only outside of this class
        return self._channel_set
    channel_set = property(_getChannelSet)

    def decode(self, *args, **kwargs):
        try:
            return self.endpoint.decodePacket(*args, **kwargs)
        except AmFastError, exc:
            # Not much we can do if packet is not decoded properly
            amfast.log_exc()
            raise exc

    def invoke(self, request):
        """Invoke an incoming request packet."""

        self.clean()
        try:
            request.channel = self
            return self.endpoint.encodePacket(request.invoke())
        except AmFastError, exc:
            amfast.log_exc()
            return self.endpoint.encodePacket(request.fail(exc))

    def getConnection(self, flex_client_id):
        lock = threading.RLock()
        lock.acquire()
        try:
            connection = self._connections.get(flex_client_id, None)
        finally:
            lock.release()

        return connection

    def connect(self, flex_client_id):
        """Add a client connection to this channel.

        Returns Connection
        """
        if self.max_connections > -1 and len(self._connections) >= self.max_connections:
            raise ChannelError("Channel '%s' is not accepting connections." % self.name)

        connection = self.connection_class(flex_client_id, self)
       
        lock = threading.RLock() 
        lock.acquire()
        try:
            self._connections[flex_client_id] = connection
        finally:
            lock.release()

        return connection

    def disconnect(self, flex_client_id):
        """Remove a client connection from this channel."""
        lock = threading.RLock()
        lock.acquire()
        try:
            if flex_client_id in self._connections:
               # Delete any subscriptions
               connection = self._connections[flex_client_id]
               subscriptions = connection.getSubscriptions()
               msg_agent = self._channel_set.message_agent
               for subscription in subscriptions:
                   msg_agent.unsubscribe(subscription.connection,
                       subscription.client_id, subscription.topic)
                   
               del self._connections[flex_client_id]
        finally:
            lock.release()

    def clean(self):
        current_time = int(time.time())
        if self._last_cleaned < current_time - self.clean_freq:
            self._last_cleaned = current_time
            t = threading.Timer(0, self._clean)
            t.start()

    def _clean(self):
        current_time = int(time.time())
        cutoff = current_time - self.time_to_live

        for connection in self._connections.values():
            if connection._last_active < cutoff:
                self.disconnect(connection.flex_client_id)
            else:
                connection.clean(current_time)

class ChannelSet(object):
    """A client can access the same RPC exposed methods
    from any of the channels in the ChannelSet.
    """

    def __init__(self, service_mapper=None, message_agent=None):
        if service_mapper is None:
            service_mapper = ServiceMapper()
        self.service_mapper = service_mapper

        if message_agent is None:
            message_agent = MessageAgent()
        self.message_agent = message_agent

        self._channels = {}

    def __iter__(self):
        return self._channels.itervalues()

    def mapChannel(self, channel):
        lock = threading.RLock()
        lock.acquire()
        try:
            self._channels[channel.name] = channel
            channel._channel_set = self
        finally:
            lock.release()

    def unMapChannel(self, channel):
        lock = threading.RLock()
        lock.acquire()
        try:
            if channel.name in self._channels:
                channel._channel_set = None
                del self._channels[channel.name]
        finally:
            lock.release()

    def getChannel(self, name):
        lock = threading.RLock()
        lock.acquire()
        try:
            channel = self._channels[name]
        finally:
            lock.release()
        return channel

    def clean(self):
        for channel in self._channels.values():
            channel.clean()
