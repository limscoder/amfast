from twisted.internet import defer, task, reactor
from twisted.web import server
from twisted.web.resource import Resource

from amfast.remoting.channel import HttpChannel, Connection
from amfast.class_def.as_types import AsNoProxy
from amfast.remoting.endpoint import AmfEndpoint
import amfast.remoting.flex_messages as messaging

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
        HttpChannel.__init__(self, name, max_connections, endpoint,
            timeout, wait_interval)

    def render_POST(self, request):
        """Process an incoming AMF packet."""
        if request.content:
            content_len = request.getHeader('Content-Length')
            raw_request = request.content.read(int(content_len))

            d = defer.Deferred()
            d.addCallbacks(self.decode, self.fail, callbackArgs=(request,), errbackArgs=(request,))
            d.addCallbacks(self.invoke, self.fail, errbackArgs=(request,))
            d.addCallbacks(self.checkComplete, self.fail, callbackArgs=(request,), errbackArgs=(request,))
            d.callback(raw_request)

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
            connection.setSessionAttr(connection.NOTIFY_KEY, False)
            _connectionLost(reason)
            request.finish()
        request.connectionLost = _connection_lost

        # This function gets called when a message is published,
        # or wait_interval is reached.
        def _notify():
            if request.finished is True:
                # Someone else has already called this function
                return

            connection.setSessionAttr(connection.NOTIFY_KEY, False)

            # Get messages and add them
            # to the response message
            messages = connection.poll()
            
            if isinstance(packet.channel.endpoint, AmfEndpoint):
                # Make sure messages are not encoded as an ArrayCollection
                messages = AsNoProxy(messages)
            message.response_msg.body.body = messages
 
            delattr(packet.response, self.MSG_NOT_COMPLETE)
            self.checkComplete(packet.response, request)

        connection.setSessionAttr(connection.NOTIFY_KEY, _notify)

        # Notify when wait_interval is reached
        if self.wait_interval > -1:
            reactor.callLater(self.wait_interval, _notify)

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

        connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.setSessionAttr(self.TWISTED_REQUEST, request)

        # Remove notify function if client drops connection.
        _connectionLost = request.connectionLost
        def _connection_lost(reason):
            connection.disconnect()
            connection.setSessionAttr(connection.NOTIFY_KEY, False)
            _connectionLost(reason)
        request.connectionLost = _connection_lost

        # This function gets called when a message is published.
        def _notify():
            if connection.active is not True:
                # Connection is disconnected
                connection.setSessionAttr(connection.NOTIFY_KEY, False)
                return

            while connection.hasMessages():
                msg = connection.popMessage()
                request.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
        connection.setSessionAttr(connection.NOTIFY_KEY, _notify)

        # Acknowledge connection
        response = msg.acknowledge()
        response.body = connection.flex_client_id
        connection.publish(response)

        self.startBeat(connection, request)

    def sendMsg(self, request, msg):
        """Send a message to the client."""
        request.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))

    def stopStream(self, msg, request):
        connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()

    def disconnect(self, connection):
        """Close response."""
        TwistedChannel.disconnect(self, connection)

        if not connection.hasSessionAttr(self.TWISTED_REQUEST):
            return

        request = connection.getSessionAttr(self.TWISTED_REQUEST)
        msg = messaging.StreamingMessage.getDisconnectMsg()
        request.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
        request.finish()

    def startBeat(self, connection, request):
        # Send out heart beat.
        looper = task.LoopingCall(None)
        def _beat():
            """Keep calling this method as long as the connection is alive."""
            if connection.active is not True:
                looper.stop()
                return
            
            request.write(chr(messaging.StreamingMessage.NULL_BYTE))

        looper.f = _beat
        looper.start(self.heart_interval)
