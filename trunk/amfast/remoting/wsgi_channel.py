"""Channels that can be used with WSGI."""
import time
import threading

import amfast
from amfast import AmFastError
from amfast.remoting.channel import ChannelSet, HttpChannel, ChannelError
import amfast.remoting.flex_messages as messaging

class WsgiChannelSet(ChannelSet):
    def __call__(self, environ, start_response):
        channel_name = environ['PATH_INFO'][1:]
        channel = self.getChannel(channel_name)
        return channel(environ, start_response)

class WsgiChannel(HttpChannel):
    """WSGI app channel."""

    def __init__(self, *args, **kwargs):

        if len(args) > 3:
            wait_interval = args[3]
        elif 'wait_interval' in kwargs:
            wait_interval = kwargs['wait_interval']
        else:
            wait_interval = 0

        if wait_interval < 0:
            # The only reliable way to detect
            # when a client has disconnected with
            # WSGI is that the 'write' function will fail.
            #
            # With long-polling, nothing is written
            # until a message is published to a client,
            # so we are unable to detect if we are
            # waiting for a message for a disconnected client.
            #
            # wait_interval must be non-negative to avoid
            # zombie threads.
            raise ChannelError('wait_interval < 0 is not supported by WsgiChannel')
            
        HttpChannel.__init__(self, *args, **kwargs)

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] != 'POST':
            return self.badMethod(start_response)

        len_str = 'CONTENT_LENGTH'
        raw_request = environ['wsgi.input'].read(int(environ[len_str]))

        try:
            request_packet = self.decode(raw_request)
        except AmFastError, exc:
            return self.badRequest(start_response, self.getBadEncodingMsg())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            return self.badServer(start_response, self.getBadServerMsg())

        try:
            content = self.invoke(request_packet)
            response = self.encode(content)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            return self.badServer(start_response, self.getBadServerMsg())

        return self.getResponse(start_response, response)

    def getResponse(self, start_response, response):
        start_response('200 OK', [
            ('Content-Type', self.CONTENT_TYPE),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badMethod(self, start_response):
        response = self.getBadMethodMsg()

        start_response('405 Method Not Allowed', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badRequest(self, start_response, response):
        start_response('400 Bad Request', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badPage(self, start_response, response):
        start_response('404 Not Found', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badServer(self, start_response, response):
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

class StreamingWsgiChannel(WsgiChannel):
    """WsgiChannel that opens a persistent connection with the client to serve messages."""

    def __init__(self, name, max_connections=-1, endpoint=None, wait_interval=0, heart_interval=30):
        WsgiChannel.__init__(self, name, max_connections=max_connections,
            endpoint=endpoint, wait_interval=wait_interval)

        self.heart_interval = heart_interval

    def __call__(self, environ, start_response):
        if environ['CONTENT_TYPE'] == self.CONTENT_TYPE:
            # Regular AMF message
            return WsgiChannel.__call__(self, environ, start_response)
        
        # Create streaming message command
        try:
            msg = messaging.StreamingMessage()
            msg.parseParams(environ['QUERY_STRING'])

            body = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
            msg.parseBody(body)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            return self.badServer(start_response, self.getBadServerMsg())

        if msg.operation == msg.OPEN_COMMAND:
            return self.startStream(environ, start_response, msg)

        if msg.operation == msg.CLOSE_COMMAND:
            return self.stopStream(msg)

        return self.badRequest(start_response, self.getBadRequestMsg('Streaming operation unknown: %s' % msg.operation))

    def startStream(self, environ, start_response, msg):
        """Start streaming response."""

        try: 
            connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            return self.badServer(start_response, self.getBadServerMsg())

        write = start_response('200 OK', [
            ('Content-Type', self.CONTENT_TYPE)
        ])

        try:
            # Send acknowledge message
            response = msg.acknowledge()
            response.body = connection.id

            try:
                bytes = messaging.StreamingMessage.prepareMsg(response, self.endpoint)
                write(bytes)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception, exc:
                amfast.log_exc(exc)
                return []

            # Start heart beat
            timer = threading.Timer(self.heart_interval, self.beat, (connection, ))
            timer.daemon = True
            timer.start()

            # Wait for new messages.
            event = threading.Event()
            connection.setNotifyFunc(event.set)
            poll_secs = float(self.poll_interval) / 1000
            while True:

                if connection.connected is False:
                    # Connection is no longer active
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    try:
                        write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
                    except:
                        # Client may have already disconnected
                        pass
                    # Stop stream
                    return []

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
                                write(bytes)
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except:
                                # Client has disconnected
                                self.channel_set.disconnect(connection)
                                return []

                        msgs = self.channel_set.subscription_manager.pollConnection(connection)
                else:
                    # Send heart beat
                    try:
                        write(chr(messaging.StreamingMessage.NULL_BYTE))
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        # Client has disconnected
                        self.channel_set.disconnect(connection)
                        return []

                # Create new event to trigger new messages or heart beats
                event = threading.Event()
                connection.setNotifyFunc(event.set)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            self.channel_set.disconnect(connection)
            return []

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

    def stopStream(self, msg):
        """Stop a streaming connection."""
        connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()
        if hasattr(connection, "notify_func") and connection.notify_func is not None:
            connection.notify_func()
