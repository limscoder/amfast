import time

import tornado.web
from tornado.ioloop import IOLoop, PeriodicCallback

import amfast
from amfast.class_def.as_types import AsNoProxy
from channel import ChannelSet, HttpChannel
from endpoint import AmfEndpoint
import flex_messages as messaging
import connection_manager as cm

class TornadoChannelSet(ChannelSet):
    def scheduleClean(self):
        cleaner = PeriodicCallback(self.clean, self.clean_freq * 1000,
            IOLoop.instance())
        cleaner.start()

    def clean(self):
        amfast.logger.debug("Cleaning connections.")

        current_time = time.time()
        for connection_id in self.connection_manager.iterConnectionIds():
            self.cleanConnection(connection_id, current_time)

    def cleanConnection(self, connection_id, current_time):
        def _callback():
            ChannelSet.cleanConnection(self, connection_id, current_time)
        IOLoop.instance().add_callback(_callback)

    def notifyConnections(self, topic, sub_topic):
        for connection_id in self.subscription_manager.iterSubscribers(topic, sub_topic):
            self.notifyConnection(connection_id)

    def notifyConnection(self, connection_id):
        def _notify():
            self._notifyConnection(connection_id)
        IOLoop.instance().add_callback(_notify)

    def _notifyConnection(self, connection_id):
        try:
            connection = self.connection_manager.getConnection(connection_id, False)
        except cm.NotConnectedError:
            return

        if connection.notify_func is not None:
            IOLoop.instance().add_callback(connection.notify_func)

class CallbackChain(object):
    """Chain together Tornado callbacks.

    When a callback completes, the next in line is called with
    the output of the previous, until the chain is completed."""

    def __init__(self):
        self.callbacks = []

    def addCallback(self, function, args=[], kwargs={}):
        self.callbacks.append({
            'function': function,
            'args': args,
            'kwargs': kwargs
        })

    def execute(self, arg=None):
        """Execute the callback chain.

        arguments:
        ============
         * arg - object, Argument to pass to 1st callback. Default = None
        """
        callback_cnt = len(self.callbacks)
        if callback_cnt < 1:
            return

        callback = self.callbacks.pop(0)

        def _execute():
            result = callback['function'](arg, *callback['args'],
                **callback['kwargs'])
            if callback_cnt > 1:
                self.execute(result)

        IOLoop.instance().add_callback(_execute)

class TornadoChannel(HttpChannel):

    # This attribute is added to packets
    # that are waiting for a long-poll
    # to receive a message.
    MSG_NOT_COMPLETE = '_msg_not_complete'

    # This attribute is added to store
    # Tornado's request handler on the packet,
    # so that it can be available to targets.
    TORNADO_REQUEST = '_tornado_request'

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1200, wait_interval=0):

        HttpChannel.__init__(self, name, max_connections, endpoint, wait_interval)

        class requestHandler(tornado.web.RequestHandler):
            """The RequestHandler class for this Channel."""

            @tornado.web.asynchronous
            def post(inner_self):
                """Process an incoming request."""
		self.processRequest(inner_self)

        self.request_handler = requestHandler

    def processRequest(self, request_handler):
        request_handler.set_header('Content-Type', self.CONTENT_TYPE)

        call_chain = CallbackChain()
        call_chain.addCallback(self.decode)
        call_chain.addCallback(self.invoke)
        call_chain.addCallback(self.checkComplete, (request_handler,))
        call_chain.execute(request_handler)

    def decode(self, request_handler):
        """Overridden to add Tornado's request object onto the packet."""
        decoded = HttpChannel.decode(self, request_handler.request.body)
        setattr(decoded, self.TORNADO_REQUEST, request_handler)
        return decoded

    def checkComplete(self, response, request_handler):
        """Checks to determine if the response message is ready
        to be returned to the client, and finishes the request if ready.
        """

        if hasattr(response, self.MSG_NOT_COMPLETE):
            # long-poll operation.
            # response is waiting for a message to be published.
            return

        if request_handler._finished is True:
            # Someone else already finished the request.
            return

        if request_handler.request.connection.stream.closed():
           # Client is not connected.
            return

        # Message is complete, encode and return
        request_handler.finish(self.encode(response))

    def waitForMessage(self, packet, message, connection):
        """Overridden to be non-blocking."""
        # Set flag so self.checkComplete
        # does not finish the message.
        setattr(packet.response, self.MSG_NOT_COMPLETE, True)

        request = getattr(packet, self.TORNADO_REQUEST)

        # This function gets called when a message is published,
        # or wait_interval is reached.
        timeout_call = None
        def _notify():
            if timeout_call is not None:
                IOLoop.instance().remove_timeout(timeout_call)

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

        # Remove notify function if client drops connection.
        request.connection.stream.set_close_callback(connection.unSetNotifyFunc())
 
        # Setup timeout
        if self.wait_interval > -1:
            timeout_call = IOLoop.instance().add_timeout(
                time.time() + self.wait_interval, _notify)

class StreamingTornadoChannel(TornadoChannel):
    """Handles streaming http connections."""

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1200, wait_interval=0, heart_interval=5):
        TornadoChannel.__init__(self, name, max_connections, endpoint,
            timeout, wait_interval)

        self.heart_interval = heart_interval
	
    def processRequest(self, request_handler):
        if request_handler.request.headers['Content-Type'] == self.CONTENT_TYPE:
	    # Regular AMF message
	    return TornadoChannel.processRequest(self, request_handler)

        msg = messaging.StreamingMessage()
	msg.parseArgs(request_handler.request.arguments)

	if msg.operation == msg.OPEN_COMMAND:
	    def _open():
	        self.startStream(msg, request_handler)
	    IOLoop.instance().add_callback(request_handler.async_callback(_open))
	elif msg.operation == msg.CLOSE_COMMAND:
            pass

    def startStream(self, msg, request_handler):
        """Get this stream rolling!"""
        connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))

        # Handle new message.
	def _notify():
            if connection.connected is False:
	        connection.unSetNotifyFunc()
		if request_handler.request.connection.stream.closed() is False:
		    msg = messaging.StreamingMessage.getDisconnectMsg()
		    self.sendMsgs((msg,), request_handler)
		    request_handler.finish()
		return
		    
	    msgs = self.channel_set.subscription_manager.pollConnection(connection)
	    self.sendMsgs(msgs, request_handler)
	connection.setNotifyFunc(_notify)

        # Handle dropped connection.
	def _connectionLost():
	    self.channel_set.disconnect(connection)
	    connection.unSetNotifyFunc()   
        request_handler.request.connection.stream.set_close_callback(_connectionLost)

	# Send acknowledge message
	response = msg.acknowledge()
	response.body = connection.id
	self.sendMsgs((response,), request_handler)

	self.startBeat(connection, request_handler)

    def sendMsgs(self, msgs, request_handler):
        """Send messages to the client."""
	for msg in msgs:
	    request_handler.write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
	request_handler.flush()

    def startBeat(self, connection, request_handler):
        beater = PeriodicCallback(None, self.heart_interval, IOLoop.instance())
        def _beat():
            if connection.connected is False:
	        beater.stop()
	    else:
		request_handler.write(chr(messaging.StreamingMessage.NULL_BYTE))
		request_handler.flush()
	beater.callback = _beat
	beater.start()
