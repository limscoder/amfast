"""Channels that can be used with WSGI."""
import time

import amfast
from amfast import AmFastError
from amfast.remoting.channel import HttpChannel
import amfast.remoting.flex_messages as messaging

class WsgiChannel(HttpChannel):
    """WSGI app channel."""

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

        return self.badRequest('Streaming operation unknown: %s' % msg.operation)

    def startStream(self, environ, start_response, msg):
        """Start streaming response."""

        try: 
            connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
            connection.connected = True
            response = msg.acknowledge()
            response.body = connection.flex_client_id
            connection.publish(response)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc()
            return self.badServer(start_response, "AMF server error.")

        start_response('200 OK', [
            ('Content-Type', self.CONTENT_TYPE)
        ])

        return self.waitForMessages(msg, connection)

    def stopStream(self, msg):
        """Stop streaming connection."""
        connection = self.channel_set.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()

    def waitForMessages(self, msg, connection):
        """Generator function that returns a message when one becomes available."""
        stop_stream = False
        total_time = 0
        while True:
            time.sleep(self.check_interval)
            total_time += self.check_interval

            try:
                if stop_stream is True:
                    return

                if connection.active is False:
                    stop_stream = True
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    yield messaging.StreamingMessage.prepareMsg(msg, self.endpoint)

                # Make sure connection stays active
                connection.touch()

                if connection.hasMessages():
                    while connection.hasMessages():
                        msg = connection.popMessage()
                        yield messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
                elif total_time > self.max_interval:
                    # Send heartbeat to tell client
                    # we're still alive
                    total_time = 0
                    yield chr(messaging.StreamingMessage.NULL_BYTE)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception, exc:
                amfast.log_exc()
                connection.disconnect()
