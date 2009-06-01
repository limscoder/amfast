"""Channels that can be used with the CherryPy framework."""

import cherrypy

from amfast.remoting.channel import HttpChannel

def amfhook():
    """Checks for POST, and stops cherrypy from processing the body."""

    cherrypy.request.process_request_body = False
    cherrypy.request.show_tracebacks = False

    if cherrypy.request.method != 'POST':
        raise cherrypy.HTTPError(405, "AMF request must use 'POST' method.");
cherrypy.tools.amfhook = cherrypy.Tool('before_request_body', amfhook, priority=0)

class CherryPyChannel(HttpChannel):
    """An AMF RPC channel that can be used with CherryPy HTTP framework.

    CherryPyChannel is deprecated.
    Please use WsgiChannel instead.
    A WsgiChannel instance can be mounted to a URL
    within CherryPy with the command cherrypy.tree.graft.

    """

    def __init__(self, *args, **kwargs):
        print "CherryPyChannel is deprecated." \
            "Use WsgiChannel instead." \
            "A WsgiChannel instance can be mounted to a URL" \
            "within CherryPy with the command cherrypy.tree.graft."
        HttpChannel.__init__(self, *args, **kwargs)

    @cherrypy.expose
    @cherrypy.tools.amfhook()
    def processMsg(self):
        try:
            c_len = int(cherrypy.request.headers['Content-Length'])
            raw_request = cherrypy.request.rfile.read(c_len)
        except KeyError:
            raw_request = cherrypy.request.rfile

        response = self.invoke(self.decode(raw_request))
        cherrypy.response.headers['Content-Type'] = self.CONTENT_TYPE
        return self.encode(response)

    def waitForMessage(self, packet, message, connection):
        cherrypy.request.timeout = 1000000
        Channel.waitForMessage(self, packet, message, connection)
