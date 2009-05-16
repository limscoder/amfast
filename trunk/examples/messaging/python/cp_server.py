"""An example server using the CherryPy web framework."""
import os
import optparse
import logging
import sys

import cherrypy

import amfast
from amfast.remoting.channel import ChannelSet
from amfast.remoting.wsgi_channel import WsgiChannel

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
    # Clients connect every x seconds
    # to polling channels to check for messages.
    # If messages are available, they are
    # returned to the client.
    polling_channel = WsgiChannel('amf-polling-channel')
    channel_set.mapChannel(polling_channel)

    # Long-poll channels do not return
    # a response to the client until
    # a message is available, or channel.max_interval
    # is reached.
    long_poll_channel = WsgiChannel('long-poll-channel', wait_interval=-1)
    channel_set.mapChannel(long_poll_channel)

    app = App()
    cherrypy.tree.graft(polling_channel, '/amf')
    cherrypy.tree.graft(long_poll_channel, '/longPoll')
    cherrypy.quickstart(app, '/', config=cp_options)

    print "Serving on %s:%s" % (options.domain, options.port)
    print "Press ctrl-c to halt."
