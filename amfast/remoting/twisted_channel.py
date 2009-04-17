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
            if request.requestHeaders.hasHeader(len_str) is True:
                content_lens = request.requestHeaders.getRawHeaders(len_str)
                raw_request = request.content.read(int(content_lens[0]))
            else:
                raw_request = request.content
            return self.invoke(raw_request)
        else:
            raise Exception("No content")
