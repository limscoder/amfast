"""Channels that can be used with WSGI."""

from amfast import AmFastError
from amfast.remoting.channel import Channel

class WsgiChannel(Channel):
    """Very basic WSGI channel."""

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] != 'POST':
            return self.badMethod(start_response)

        len_str = 'CONTENT-LENGTH'
        if len_str in environ:
            raw_request = environ['wsgi.input'].read(int(len_str))
        else:
            raw_request = environ['wsgi.input']

        try:
            request_packet = self.decode(raw_request)
        except AmFastError, exc:
            return self.badRequest(start_response, "AMF packet could not be decoded.")
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return self.badServer(start_response, "AMF server error.")

        try:
            content = self.invoke(request_packet)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return self.badServer(start_response, "AMF server error.")

        return self.getResponse(start_response, content)

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
