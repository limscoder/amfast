"""Channels that can be used with WSGI."""
import time

import amfast
from amfast import AmFastError
from amfast.remoting.channel import HttpChannel, Connection, StreamingConnection, ChannelError
import amfast.remoting.flex_messages as messaging

class WsgiChannel(HttpChannel):
    """WSGI app channel."""

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1800, connection_class=Connection, wait_interval=0,
        check_interval=0.1):

        if wait_interval < 0:
            # There is no reliable way to detect
            # when a client has disconnected,
            # so if wait_interval < 0, threads will
            # wait forever.
            raise ChannelError('wait_interval < 0 is not supported by WsgiChannel')
            
        HttpChannel.__init__(self, name, max_connections=max_connections,
            endpoint=endpoint, timeout=timeout, connection_class=connection_class,
            wait_interval=wait_interval, check_interval=check_interval)

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] != 'POST':
            return self.badMethod(start_response)

        len_str = 'CONTENT_LENGTH'
        raw_request = environ['wsgi.input'].read(int(environ[len_str]))

        try:
            request_packet = self.decode(raw_request)
        except AmFastError, exc:
            return self.badRequest(start_response, "AMF packet could not be decoded.")
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        try:
            content = self.invoke(request_packet)
            response = self.encode(content)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        return self.getResponse(start_response, response)

    def getResponse(self, start_response, response):
        start_response('200 OK', [
            ('Content-Type', self.CONTENT_TYPE),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badMethod(self, start_response):
        response = "405 Method Not Allowed\n\nAMF request must use 'POST' method."

        start_response('405 Method Not Allowed', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badRequest(self, start_response, msg):
        response = "400 Bad Request\n\n%s" % msg

        start_response('400 Bad Request', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badPage(self, start_response, msg):
        response = "404 Not Found\n\n%s" % msg

        start_response('404 Not Found', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

    def badServer(self, start_response, msg):
        response = "500 Internal Server Error\n\n%s" % msg

        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response)))
        ])

        return [response]

class StreamingWsgiChannel(WsgiChannel):
    """WsgiChannel that opens a persistent connection with the client to serve messages."""

    WRITE_ATTR = "_write_method"

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1800, wait_interval=0,  thread_safe_write=True):
        WsgiChannel.__init__(self, name, max_connections, endpoint,
            timeout, StreamingConnection, wait_interval, check_interval)

        self.thread_safe_write = thread_safe_write # True if write() can be called from a different thread

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
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        if msg.operation == msg.OPEN_COMMAND:
            return self.startStream(environ, start_response, msg)

        if msg.operation == msg.CLOSE_COMMAND:
            return self.stopStream(msg)

        return self.badRequest(start_response, 'Streaming operation unknown: %s' % msg.operation)

    def publish(self, connection, msg):
        """Send response."""
        write = connection.getSessionAttr(self.WRITE_ATTR)
        try:
            bytes = messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        try:
            write(bytes)
        except:
            connection.disconnect()

    def disconnect(self, connection):
        WsgiChannel.disconnect(self, connection)
        connection.connected = False
        if connection.hasSessionAttr(self.WRITE_ATTR):
            connection.delSessionAttr(self.WRITE_ATTR)

    def startStream(self, environ, start_response, msg):
        """Start streaming response."""

        try: 
            connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        write = start_response('200 OK', [
            ('Content-Type', self.CONTENT_TYPE)
        ])

        try:
            # Set write method, so we can write to it later on
            connection.connected = True
            connection.getSessionAttr(self.WRITE_ATTR, write)
            if self.thread_safe_write is True:
                connection.channel_publish = True
            else:
                connection.channel_publish = False

            response = msg.acknowledge()
            response.body = connection.flex_client_id
            connection.publish(response)

            if self.thread_safe_write is True:
                return self.startBeat(connection)
            else:
                # WSGI servers that can't do
                # thread-safe write(), must poll
                # for messages.
                return self.writeWait(msg, connection)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc()
            connection.disconnect()
            return []

    def stopStream(self, msg):
        """Stop streaming connection."""
        connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()

    def startBeat(self, connection):
        write = connection.getSessionAttr(self.WRITE_ATTR)

        while True:
            try:
                time.sleep(connection.heart_interval)
            
                if connection.active is False or connection.connected is False:
                    stop_stream = True
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    try:
                        write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
                    except:
                        pass
                    return []
                else:
                    try:
                        write(chr(messaging.StreamingMessage.NULL_BYTE))
                    except:
                        connection.disconnect()
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception, exc:
                amfast.log_exc()
                connection.disconnect()

    def writeWait(self, msg, connection):
        """Generator function that returns a message when one becomes available."""
        write = connection.getSessionAttr(self.WRITE_ATTR)

        total_time = 0
        while True:
            try:
                time.sleep(self.check_interval)
                total_time += self.check_interval

                if connection.active is False or connection.connected is False:
                    stop_stream = True
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    try:
                        write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
                    except:
                        pass
                    return []

                if connection.hasMessages():
                    while connection.hasMessages():
                        msg = connection.popMessage()
                        try:
                            write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
                        except:
                            connection.disconnect()
                            break
                elif total_time > connection.heart_interval:
                    # Send heartbeat to tell client
                    # we're still alive
                    total_time = 0
                    try:
                        write(chr(messaging.StreamingMessage.NULL_BYTE))
                    except:
                        connection.disconnect()
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception, exc:
                amfast.log_exc()
                connection.disconnect()
