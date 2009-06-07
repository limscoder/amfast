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
    """An AMF messaging channel that can be used with CherryPy HTTP framework.

    Instantiate a CherryPyChannel object and
    mount the processMsg method to the URL where
    AMF messaging should be available from. 

    CherryPyChannel does not support HTTP streaming.
    Use WsgiChannel to achieve HTTP streaming.

    A WsgiChannel instance can be mounted to a URL
    within CherryPy with the command cherrypy.tree.graft.

    """

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
