"""Channels that can be used with the CherryPy framework."""
import threading

import cherrypy
import cherrypy.process.plugins as cp_plugins

import amfast
import amfast.remoting.flex_messages as messaging
from amfast.remoting.channel import ChannelSet, HttpChannel, ChannelError

def amfhook():
    """Checks for POST, and stops cherrypy from processing the body."""

    cherrypy.request.process_request_body = False
    cherrypy.request.show_tracebacks = False

    if cherrypy.request.method != 'POST':
        raise cherrypy.HTTPError(405, "405 Method Not Allowed\n\nAMF request must use 'POST' method.");
cherrypy.tools.amfhook = cherrypy.Tool('before_request_body', amfhook, priority=0)

class CherryPyChannelSet(ChannelSet):
    """A ChannelSet for use with CherryPy."""

    def __init__(self, *args, **kwargs):
        self.clean_scheduled = False
        ChannelSet.__init__(self, *args, **kwargs)

    def scheduleClean(self):
        """Overridden to use CherryPy's Monitor functionality."""
        if self.clean_scheduled is False:
            cleaner = cp_plugins.Monitor(cherrypy.engine, self.clean, self.clean_freq)
            cleaner.name = "ConnectionCleaner"
            cleaner.subscribe()
            self.clean_scheduled = True

    def mapChannel(self, channel):
        """Overridden so that channel is added as an attribute."""
        if hasattr(self, channel.name):
            raise ChannelError("Reserved attribute name '%s' cannot be used as a channel name." % channel.name)

        ChannelSet.mapChannel(self, channel)

        setattr(self, channel.name, channel.__call__)

class CherryPyChannel(HttpChannel):
    """An AMF messaging channel that can be used with CherryPy HTTP framework.

    Instantiate a CherryPyChannel object and
    mount the __call__ method to the URL where
    AMF messaging should be available from. 

    You can also use a WsgiChannel instance by
    grafting it to the CherryPy tree with
    the command cherrypy.tree.graft.

    Using WsgiChannel will be more efficient, but you
    won't have access to any of CherryPy's built-in tools
    such as cookie-based sessions.

    """

    @cherrypy.expose
    @cherrypy.tools.amfhook()
    def __call__(self):
        try:
            c_len = int(cherrypy.request.headers['Content-Length'])
            raw_request = cherrypy.request.rfile.read(c_len)
        except KeyError:
            raw_request = cherrypy.request.rfile

        response = self.invoke(self.decode(raw_request))
        cherrypy.response.headers['Content-Type'] = self.CONTENT_TYPE
        return self.encode(response)

class StreamingCherryPyChannel(CherryPyChannel):
    """Allows HTTP streaming."""

    def __init__(self, name, max_connections=-1, endpoint=None,
        wait_interval=0, heart_interval=30):
        CherryPyChannel.__init__(self, name, max_connections=max_connections,
            endpoint=endpoint, wait_interval=wait_interval)

        self.heart_interval = heart_interval

    @cherrypy.expose
    @cherrypy.tools.amfhook()
    def __call__(self, command=None, version=None):
        if cherrypy.request.headers['Content-Type'] == self.CONTENT_TYPE:
            # Regular AMF message
            return CherryPyChannel.__call__(self)

        # Create streaming message command
        cherrypy.response.stream = True
        try:
            msg = messaging.StreamingMessage()
            msg.parseParams(cherrypy.request.query_string)

            c_len = int(cherrypy.request.headers['Content-Length'])
            body = cherrypy.request.rfile.read(c_len)
            msg.parseBody(body)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            raise ChannelError("AMF server error.")

        if msg.operation == msg.OPEN_COMMAND:
            return self.startStream(msg)

        if msg.operation == msg.CLOSE_COMMAND:
            return self.stopStream(msg)

        raise ChannelError('Http streaming operation unknown: %s' % msg.operation)

    def startStream(self, msg):
        """Returns an iterator for streaming."""

        try:
            connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            raise ChannelError('Http streaming operation unknown: %s' % msg.operation)

        cherrypy.response.headers['Content-Type'] = self.CONTENT_TYPE

        try:
            # Start heart beat
            timer = threading.Timer(self.heart_interval, self.beat, (connection, ))
            timer.daemon = True
            timer.start()

            # Wait for new messages.
            inited = False
            event = threading.Event()
            connection.setNotifyFunc(event.set)
            poll_secs = float(self.poll_interval) / 1000
            while True:

                if connection.connected is False:
                    # Connection is no longer active
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    try:
                        yield messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
                    finally:
                        # Client may have already disconnected
                        return

                if inited is False:
                    # Send acknowledge message
                    response = msg.acknowledge()
                    response.body = connection.id

                    bytes = messaging.StreamingMessage.prepareMsg(response, self.endpoint)
                    inited = True
                    yield bytes
 
                if self.channel_set.notify_connections is True:
                    # Block until notification of new message
                    event.wait()
                else:
                    # Block until poll_interval is reached
                    event.wait(poll_secs)

                # Message has been published,
                # or it's time for a heart beat

                # Remove notify_func so that
                # New messages don't trigger event.
                connection.unSetNotifyFunc()

                msgs = self.channel_set.subscription_manager.pollConnection(connection)
                if len(msgs) > 0:
                    while len(msgs) > 0:
                        # Dispatch all messages to client
                        for msg in msgs:
                            try:
                                bytes = messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except Exception, exc:
                                amfast.log_exc(exc)
                                self.channel_set.disconnect(connection)
                                break

                            try:
                                yield bytes
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except:
                                # Client has disconnected
                                self.channel_set.disconnect(connection)
                                return

                        msgs = self.channel_set.subscription_manager.pollConnection(connection)
                else:
                    # Send heart beat
                    try:
                        yield chr(messaging.StreamingMessage.NULL_BYTE)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        # Client has disconnected
                        self.channel_set.disconnect(connection)
                        return

                # Create new event to trigger new messages or heart beats
                event = threading.Event()
                connection.setNotifyFunc(event.set)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            self.channel_set.disconnect(connection)
            return

    def stopStream(self, msg):
        """Stop a streaming connection."""

        connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()
        if hasattr(connection, "notify_func") and connection.notify_func is not None:
            connection.notify_func()

    def beat(self, connection):
        """Send a heart beat."""

        if hasattr(connection, "notify_func") and connection.notify_func is not None:
            connection.notify_func()
        else:
            return

        # Create timer for next beat
        timer = threading.Timer(self.heart_interval, self.beat, (connection, ))
        timer.daemon = True
        timer.start()
