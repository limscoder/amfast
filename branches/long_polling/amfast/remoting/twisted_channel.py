from twisted.internet import defer, task
from twisted.web import server
from twisted.web.resource import Resource

from amfast.remoting.channel import Channel
from amfast.class_def.as_types import AsNoProxy
from amfast.remoting.endpoint import AmfEndpoint

class TwistedChannel(Resource, Channel):
    """An AMF RPC channel that can be used with Twisted Web."""

    def __init__(self, name, *args, **kwargs):
        Resource.__init__(self)
        Channel.__init__(self, name, *args, **kwargs)

    # This attribute is added to packets
    # that are waiting for a long-poll
    # to receive a message.
    MSG_NOT_COMPLETE = '_msg_not_complete'

    # This attribute is added to store
    # Twisted's request var on the packet,
    # so that it can be availalbe to targets.
    MSG_REQUEST = '_msg_request'

    def render_POST(self, request):
        """Process and incoming AMF packet."""
        if request.content:
            len_str = 'Content-Length'
            content_len = request.getHeader(len_str)
            if content_len is not None:
                raw_request = request.content.read(int(content_len))
            else:
                raw_request = request.content

            d = defer.Deferred()
            d.addCallback(self.decode, request)
            d.addCallback(self.invoke)
            d.addCallback(self._checkComplete)
            d.callback(raw_request)

            return server.NOT_DONE_YET

    def decode(self, raw_request, request):
        """Overridden to add Twisted's request object onto the packet."""
        decoded = Channel.decode(self, raw_request)
        setattr(decoded, self.MSG_REQUEST, request)
        return decoded

    def invoke(self, packet):
        """Overridden to add Twisted's request object onto the response packet."""
        response = Channel.invoke(self, packet)
        setattr(response, self.MSG_REQUEST, getattr(packet, self.MSG_REQUEST))
        return response

    def _checkComplete(self, response):
        """Checks to determine if the response message is ready
        to be returned to the client, and defers the response if
        ready.
        """

        if hasattr(response, self.MSG_NOT_COMPLETE):
            # Message is waiting on something
            return

        # Message is complete, encode and return
        d = defer.Deferred()
        d.addCallback(self.encode)
        d.addCallback(self._finish, getattr(response, self.MSG_REQUEST))
        d.callback(response)

    def _finish(self, raw_response, request):
        """Send response to client when message is complete."""
        request.setHeader('Content-Type', self.CONTENT_TYPE)
        request.write(raw_response)
        request.finish()

    def waitForMessage(self, packet, message, connection):
        """Overridden to be non-blocking."""
        # Set flag so self._finish
        # does not get called when
        # response packet is returned 
        # from self.invoke.
        setattr(packet.response, self.MSG_NOT_COMPLETE, True)

        # Twisted Request obj is added to packet.response
        # in self.invoke, but only AFTER
        # the invocation is complete.
        #
        # This method will be called during
        # invocation, so we need to add it 
        # here too.
        setattr(packet.response, self.MSG_REQUEST, getattr(packet, self.MSG_REQUEST))

        looper = task.LoopingCall(None)

        total = [0] # Lame hack to be able to increment within closure. There has to be a better way...
        def _checkMsgs():
            """Keep calling this method until we find messages."""

            if not connection.hasMessages() and not total[0] > self.max_interval:
                # We're still looking for a message.
                total[0] += self.check_interval
                return

            # At least one message is present
            # or we've hit max_interval
            looper.stop()

            # Get messages and add them
            # to the response message
            messages = connection.poll()
            
            if isinstance(packet.channel.endpoint, AmfEndpoint):
                # Make sure messages are not encoded as an ArrayCollection
                messages = AsNoProxy(messages)
            message.response_msg.body.body = messages
 
            delattr(packet.response, self.MSG_NOT_COMPLETE)
            self._checkComplete(packet.response)

        looper.f = _checkMsgs
        looper.start(self.check_interval)
