"""An example server using the CherryPy web framework.

This example uses a WsgiChannel, grafted onto the CherryPy tree.

To run the example execute the command:
    python cp_server.py
"""
import os
import optparse
import logging
import sys

import cherrypy

import amfast
from amfast.remoting.channel import ChannelSet
from amfast.remoting.wsgi_channel import StreamingWsgiChannel

class App(object):
    """Base web app."""
    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect('/messaging.html')

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
   
    # Send log messages to STDOUT
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    amfast.logger.addHandler(handler)

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

    channel_set = ChannelSet()
    stream_channel = StreamingWsgiChannel('stream-channel')
    channel_set.mapChannel(stream_channel)

    app = App()
    cherrypy.tree.graft(stream_channel, '/amf')
    cherrypy.quickstart(app, '/', config=cp_options)

    print "Serving on %s:%s" % (options.domain, options.port)
    print "Press ctrl-c to halt."
