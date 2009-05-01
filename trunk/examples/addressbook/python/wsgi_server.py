"""An example server using the CherryPy web framework."""
import os
import optparse
from wsgiref import simple_server

import amfast
from amfast.remoting.channel import ChannelSet
from amfast.remoting.wsgi_channel import WsgiChannel
import utils

class App(object):
    def __init__(self):
        self.channel_set = ChannelSet()
        rpc_channel = WsgiChannel('amf-channel')
        self.channel_set.mapChannel(rpc_channel)
        utils.setup_channel_set(self.channel_set)

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].replace('/', '')

        if path == 'amf':
            channel = self.channel_set.getChannel('amf-channel')
            return channel(environ, start_response)
        else:
            channel = self.channel_set.getChannel('amf-channel')
            return channel.badPage(start_response, 'Page does not exist.')

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

    server = simple_server.WSGIServer((options.domain, int(options.port)),
        simple_server.WSGIRequestHandler)

    server.set_app(App())

    try:
        print "Serving on %s:%s" % (options.domain, options.port)
        print "Press ctrl-c to halt."
        server.serve_forever()
    except KeyboardInterrupt:
        pass
