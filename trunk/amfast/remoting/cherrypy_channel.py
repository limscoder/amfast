"""Channels that can be used with the CherryPy framework."""

import cherrypy

from amfast.remoting.channel import Channel

def amfhook():
    """Checks for POST, and stops cherrypy from processing the body."""
    cherrypy.request.process_request_body = False
    cherrypy.request.show_tracebacks = False

    if cherrypy.request.method != 'POST':
        raise cherrypy.HTTPError(405, "AMF request must use 'POST' method.");
cherrypy.tools.amfhook = cherrypy.Tool('before_request_body', amfhook, priority=0)

class CherryPyChannel(Channel):
    """An AMF RPC channel that can be used with CherryPy."""
    @cherrypy.expose
    @cherrypy.tools.amfhook()
    def invoke(self):
        try:
            c_len = int(cherrypy.request.headers['Content-Length'])
            raw_request = cherrypy.request.rfile.read(c_len)
        except KeyError:
            raw_request = cherrypy.request.rfile

        return Channel.invoke(self, raw_request)
