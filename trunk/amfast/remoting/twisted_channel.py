import time

from twisted.internet import defer, task, reactor
from twisted.web import server
from twisted.web.resource import Resource

import amfast
from amfast.class_def.as_types import AsNoProxy
from channel import ChannelSet, HttpChannel
from endpoint import AmfEndpoint
import flex_messages as messaging
import connection_manager as cm

class TwistedChannelSet(ChannelSet):
    """A ChannelSet optimized for use with Twisted."""

    def render_POST(self, request):
        channel_name = request.path[1:]
        channel = self.getChannel(channel_name)
        return channel.render_POST(request)

    def scheduleClean(self):
        reactor.callLater(self.clean_freq, self.clean)

    def notifyConnections(self, topic, sub_topic):
        reactor.callLater(0.1, self._notifyConnections, topic, sub_topic)

    def _notifyConnections(self, topic, sub_topic):
        for connection_id in self.subscription_manager.iterSubscribers(topic, sub_topic):
            try:
                connection = self.connection_manager.getConnection(connection_id, False)
            except cm.NotConnectedError:
                continue

            if connection.notify_func is not None:
                reactor.callLater(0.1, connection.notify_func)

    def clean(self):
        amfast.logger.debug("Cleaning connections.")

        current_time = time.time()
        deferreds = []
        for connection_id in self.connection_manager.iterConnectionIds():
            d = defer.Deferred()
            d.addCallbacks(self.cleanConnection, callbackArgs=(current_time,))
            reactor.callLater(0.3, d.callback, connection_id)

        if len(deferreds) > 0:
            def _scheduleClean(val):
                self.scheduleClean()

            deferredList = defer.DeferredList(deferreds)
            deferredList.addCallback(self.scheduleClean)
        else:
            self.scheduleClean()

class TwistedChannel(Resource, HttpChannel):
    """An AMF messaging channel that can be used with Twisted Web."""

    # This attribute is added to packets
    # that are waiting for a long-poll
    # to receive a message.
    MSG_NOT_COMPLETE = '_msg_not_complete'

    # This attribute is added to store
    # Twisted's request var on the packet,
    # so that it can be available to targets.
    TWISTED_REQUEST = '_twisted_request'

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1200, wait_interval=0):

        Resource.__init__(self)
        HttpChannel.__init__(self, name, max_connections, endpoint, wait_interval)

    def render_POST(self, request):
        """Process an incoming AMF packet."""
        if request.content:
            d = defer.Deferred()
            d.addCallbacks(request.content.read, self.fail, errbackArgs=(request,))
            d.addCallbacks(self.decode, self.fail, callbackArgs=(request,), errbackArgs=(request,))
            d.addCallbacks(self.invoke, self.fail, errbackArgs=(request,))
            d.addCallbacks(self.checkComplete, self.fail, callbackArgs=(request,), errbackArgs=(request,))
            d.callback(int(request.getHeader('Content-Length')))

            request.setHeader('Content-Type', self.CONTENT_TYPE)
            return server.NOT_DONE_YET

    def decode(self, raw_request, request):
        """Overridden to add Twisted's request object onto the packet."""
        decoded = HttpChannel.decode(self, raw_request)
        setattr(decoded, self.TWISTED_REQUEST, request)
        return decoded

    def getDeferred(self, msg):
        """Returns a Deferred object if a message contains a Deferred in its body,
        or False if message is not deferred.
        """
        if msg.is_flex_msg:
            body = msg.body.body
            if isinstance(body, defer.Deferred):
                return body
        else:
            body = msg.body
            if isinstance(body, defer.Deferred):
                return body
        return False

    def completeDeferreds(self, results, response, request, deferred_msgs):
        """A response's deferred methods have completed."""
        for i, result in enumerate(results):
            msg = deferred_msgs[i]

            if result[0] is False:
                # Invokation failed
                msg.convertFail(result[1].value)
            else:
                if msg.is_flex_msg:
                    msg.body.body = result[1]
                else:
                    msg.body = result[1]
 
        d = defer.Deferred()
        d.addCallbacks(self.encode, self.fail, errbackArgs=(request,))
        d.addCallbacks(self.finish, self.fail, callbackArgs=(request,),
            errbackArgs=(request,))
        d.callback(response) 

    def checkComplete(self, response, request):
        """Checks to determine if the response message is ready
        to be returned to the client, and defers the response if
        ready.
        """

        if hasattr(response, self.MSG_NOT_COMPLETE):
            # long-poll operation.
            # response is waiting for a message to be published.
            return

        # Check for deferred messages
        deferreds = []
        deferred_msgs = []
        for msg in response.messages:
            deferred = self.getDeferred(msg)
            if deferred is not False:
                deferreds.append(deferred)
                deferred_msgs.append(msg)

        if len(deferreds) > 0:
            dl = defer.DeferredList(deferreds)
            dl.addCallbacks(self.completeDeferreds, self.fail,
                callbackArgs=(response, request, deferred_msgs), errbackArgs=(request,))
            return

        # Message is complete, encode and return
        d = defer.Deferred()
        d.addCallbacks(self.encode, self.fail, errbackArgs=(request,))
        d.addCallbacks(self.finish, self.fail, callbackArgs=(request,), errbackArgs=(request,))
        d.callback(response)

    def finish(self, raw_response, request):
        """Send response to client when message is complete."""
        request.write(raw_response)
        request.finish()

    def fail(self, failure, request, code=500, message='Internal Server Error'):
        request.setResponseCode(500, message)
        self.finish(message, request)

    def waitForMessage(self, packet, message, connection):
        """Overridden to be non-blocking."""
        # Set flag so self.finish
        # does not get called when
        # response packet is returned 
        # from self.invoke.
        setattr(packet.response, self.MSG_NOT_COMPLETE, True)

        request = getattr(packet, self.TWISTED_REQUEST)

        # Remove notify function if client drops connection.
        _connectionLost = request.connectionLost
        def _connection_lost(reason):
            connection.unSetNotifyFunc()
            _connectionLost(reason)
            request.finish()
        request.connectionLost = _connection_lost

        # This function gets called when a message is published,
        # or wait_interval is reached.
        timeout_call = None
        def _notify():
            if request.finished:
                # Someone else has already called this function,
                # or twisted has finished the request for some other reason.
                return

            if timeout_call is not None and timeout_call.active():
                timeout_call.cancel()
            
            connection.unSetNotifyFunc()

            # Get messages and add them
            # to the response message
            messages = self.channel_set.subscription_manager.pollConnection(connection)
            
            if isinstance(packet.channel.endpoint, AmfEndpoint):
                # Make sure messages are not encoded as an ArrayCollection
                messages = AsNoProxy(messages)
            message.response_msg.body.body = messages
 
            delattr(packet.response, self.MSG_NOT_COMPLETE)
            self.checkComplete(packet.response, request)

        connection.setNotifyFunc(_notify)

        # Notify when wait_interval is reached
        if self.wait_interval > -1:
            timeout_call = reactor.callLater(self.wait_interval, _notify)

class StreamingTwistedChannel(TwistedChannel):
    """Handles streaming http connections."""

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1200, wait_interval=0, heart_interval=5):
        TwistedChannel.__init__(self, name, max_connections, endpoint,
            timeout, wait_interval)

        self.heart_interval = heart_interval

    def render_POST(self, request):
        """Process an incoming AMF packet."""

        if request.getHeader('Content-Type') == self.CONTENT_TYPE:
            # Regular AMF message
            return TwistedChannel.render_POST(self, request)

        # Create streaming message command
        msg = messaging.StreamingMessage()
        msg.parseArgs(request.args)

        d = defer.Deferred()
        if msg.operation == msg.OPEN_COMMAND:
            d.addCallbacks(self.startStream, self.fail, callbackArgs=(request,), errbackArgs=(request,))
            d.callback(msg)
            return server.NOT_DONE_YET
        if msg.operation == msg.CLOSE_COMMAND:
            d.addCallbacks(self.stopStream, self.fail, callbackArgs=(request,), errbackArgs=(request,))
            d.callback(msg)
            return server.NOT_DONE_YET

    def startStream(self, msg, request):
        """Get this stream rolling!"""
        connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))

        # Remove notify function if client drops connection.
        _connectionLost = request.connectionLost
        def _connection_lost(reason):
            self.channel_set.disconnect(connection)
            connection.unSetNotifyFunc()
            _connectionLost(reason)
        request.connectionLost = _connection_lost

        # This function gets called when a message is published.
        def _notify():
            if connection.connected is False:
                # Connection is disconnected
                connection.unSetNotifyFunc()
                msg = messaging.StreamingMessage.getDisconnectMsg()
                request.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
                request.finish()
                return

            msgs = self.channel_set.subscription_manager.pollConnection(connection)
            for msg in msgs:
                request.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
        connection.setNotifyFunc(_notify)

        # Acknowledge connection
        response = msg.acknowledge()
        response.body = connection.id
        self.sendMsg(request, response)

        self.startBeat(connection, request)

    def sendMsg(self, request, msg):
        """Send a message to the client."""
        request.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))

    def stopStream(self, msg, request):
        connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        self.channel_set.disconnect(connection)

    def startBeat(self, connection, request):
        # Send out heart beat.
        looper = task.LoopingCall(None)
        def _beat():
            """Keep calling this method as long as the connection is alive."""
            if connection.connected is False:
                looper.stop()
                return
            
            request.write(chr(messaging.StreamingMessage.NULL_BYTE))

        looper.f = _beat
        looper.start(self.heart_interval)
