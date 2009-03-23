"""An example server using the CherryPy web framework."""
import os
import optparse

import cherrypy

import amfast.remoting

import utils

def amfhook():
    """Checks for POST, and stops cherrypy from processing the body."""
    cherrypy.request.process_request_body = False
    cherrypy.request.show_tracebacks = False

    if cherrypy.request.method != 'POST':
        raise cherrypy.HTTPError(405, "AMF request must use 'POST' method.");
cherrypy.tools.amfhook = cherrypy.Tool('before_request_body', amfhook, priority=0)

class App(object):
    """Controller class that directs requests to the Gateway."""
    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect('/addressbook.html')

    @cherrypy.expose
    @cherrypy.tools.amfhook()
    def amfGateway(self):
        c_len = int(cherrypy.request.headers['Content-Length'])
        raw_request = cherrypy.request.rfile.read(c_len)
        return self.gateway.process_packet(raw_request)

if __name__ == '__main__':
    usage = """usage: %s [options]""" % __file__
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-p", default=8000,
        dest="port", help="port number to serve")
    parser.add_option("-d", default="localhost",
        dest="domain", help="domain to serve")
    parser.add_option("-l", action="store_true",
        dest="log_debug", help="log debugging output")
    (options, args) = parser.parse_args()

    amfast.log_debug = options.log_debug

    gateway = amfast.remoting.Gateway()
    utils.setup_gateway(gateway)

    # Start server
    cp_options = {
        'global':
        {
            'server.socket_port': int(options.port),
            'server.socket_host': str(options.domain),
        },
        '/':
        {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.join(os.getcwd(), '../flex/deploy')
        }
    }

    app = App()
    app.gateway = gateway
    cherrypy.quickstart(app, '/', config=cp_options)

    print "Serving on %s:%s" % (options.domain, options.port)
    print "Press ctrl-c to halt."
