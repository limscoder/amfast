"""An example server using the CherryPy web framework."""
import os
import optparse
import logging
import sys

import cherrypy

import amfast
from amfast.remoting.cherrypy_channel import CherryPyChannel, CherryPyChannelSet

class App(CherryPyChannelSet):
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

    # Create ChannelSet
    channel_set = App(notify_connections=True)

    # Clients connect every x seconds
    # to polling channels to check for messages.
    # If messages are available, they are
    # returned to the client.
    polling_channel = CherryPyChannel('amf')
    channel_set.mapChannel(polling_channel)

    # Long-poll channels do not return
    # a response to the client until
    # a message is available, or channel.max_interval
    # is reached.
    long_poll_channel = CherryPyChannel('longPoll', wait_interval=90)
    channel_set.mapChannel(long_poll_channel)

    # Start serving
    cherrypy.quickstart(channel_set, '/', config=cp_options)

    print "Serving on %s:%s" % (options.domain, options.port)
    print "Press ctrl-c to halt."
