from twisted.internet import threads
from twisted.web import server
from twisted.web.resource import Resource

from amfast.remoting.channel import Channel

class TwistedChannel(Resource, Channel):
    """An AMF RPC channel that can be used with Twisted Web."""

    def __init__(self, name, *args, **kwargs):
        Resource.__init__(self)
        Channel.__init__(self, name, *args, **kwargs)

    def render_POST(self, request):
        if request.content:
            len_str = 'Content-Length'
            content_len = request.getHeader(len_str)
            if content_len is not None:
                raw_request = request.content.read(int(content_len))
            else:
                raw_request = request.content

            threads.deferToThread(self._processMsg, request, raw_request).addCallback(self._finish)
            return server.NOT_DONE_YET

    def _processMsg(self, request, raw_request):
        response = self.invoke(self.decode(raw_request))
        return (request, self.encode(response))

    def _finish(self, data):
        request = data[0]
        request.setHeader('Content-Type', self.CONTENT_TYPE)
        request.write(data[1])
        request.finish()

