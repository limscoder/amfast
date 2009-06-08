"""Channels that can be used with WSGI."""
import time
import threading

import amfast
from amfast import AmFastError
from amfast.remoting.channel import HttpChannel, Connection, ChannelError
import amfast.remoting.flex_messages as messaging

class WsgiChannel(HttpChannel):
    """WSGI app channel."""

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1200, wait_interval=0):

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
            
        HttpChannel.__init__(self, name, max_connections=max_connections,
            endpoint=endpoint, timeout=timeout, wait_interval=wait_interval)

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

    def __init__(self, name, max_connections=-1, endpoint=None,
        timeout=1200, wait_interval=0, heart_interval=30):
        WsgiChannel.__init__(self, name, max_connections, endpoint,
            timeout, wait_interval)

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
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        if msg.operation == msg.OPEN_COMMAND:
            return self.startStream(environ, start_response, msg)

        if msg.operation == msg.CLOSE_COMMAND:
            return self.stopStream(msg)

        return self.badRequest(start_response, 'Streaming operation unknown: %s' % msg.operation)

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
            # Send acknowledge message
            response = msg.acknowledge()
            response.body = connection.flex_client_id

            try:
                bytes = messaging.StreamingMessage.prepareMsg(response, self.endpoint)
                write(bytes)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception, exc:
                amfast.log_exc()
                return []

            # Start heart beat
            timer = threading.Timer(self.heart_interval, self.beat, (connection, ))
            timer.start()

            # Wait for new messages.
            event = threading.Event()
            connection.setSessionAttr(connection.NOTIFY_KEY, event.set)
            while True:
                if connection.active is not True:
                    # Connection is no longer active
                    connection.setSessionAttr(connection.NOTIFY_KEY, False)
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    try:
                        write(messaging.StreamingMessage.prepareMsg(msg, self.endpoint))
                    except:
                        # Client may have already disconnected
                        pass
                    # Stop stream
                    return []
 
                # Block until new message
                event.wait()

                # Message has been published,
                # or it's time for a heart beat
                connection.setSessionAttr(connection.NOTIFY_KEY, False)
                new_msg = connection.hasMessages()
                if new_msg is True:
                    # Send message
                    while new_msg is True:
                        msg = connection.popMessage()

                        try:
                            bytes = messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except Exception, exc:
                            amfast.log_exc()
                            connection.disconnect()
                            break

                        try:
                            write(bytes)
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except:
                            # Client has disconnected
                            connection.disconnect()
                            return []

                        new_msg = connection.hasMessages()
                else:
                    # Send heart beat
                    try:
                        write(chr(messaging.StreamingMessage.NULL_BYTE))
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        # Client has disconnected
                        connection.disconnect()
                        return []

                # Create new event to trigger new messages or heart beats
                event = threading.Event()
                connection.setSessionAttr(connection.NOTIFY_KEY, event.set)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc()
            connection.disconnect()
            return []

    def beat(self, connection):
        """Send a heart beat."""
        if connection.active is not True:
            # Client is disconnected
            return

        notify_func = connection.getSessionAttr(connection.NOTIFY_KEY)
        if notify_func is not False:
            notify_func()

        # Create timer for next beat
        timer = threading.Timer(self.heart_interval, self.beat, (connection, ))
        timer.start()

    def stopStream(self, msg):
        """Stop a streaming connection."""
        connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()
        notify_func = connection.getSessionAttr(connect.NOTIFY_KEY)
        if notify_func is not False:
            notify_func()
