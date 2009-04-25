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

            return self.invoke(self.decode(raw_request))
        else:
            raise Exception("No content")
