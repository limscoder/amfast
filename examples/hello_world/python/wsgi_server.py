"""An example server using the CherryPy web framework."""
import os
import optparse
from wsgiref import simple_server

import amfast
from amfast.remoting.wsgi_channel import WsgiChannelSet, WsgiChannel
import utils

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

    channel_set = WsgiChannelSet()
    rpc_channel = WsgiChannel('amf')
    channel_set.mapChannel(rpc_channel)
    utils.setup_channel_set(channel_set)

    server = simple_server.WSGIServer((options.domain, int(options.port)),
        simple_server.WSGIRequestHandler)

    server.set_app(channel_set)

    try:
        print "Serving on %s:%s" % (options.domain, options.port)
        print "Press ctrl-c to halt."
        server.serve_forever()
    except KeyboardInterrupt:
        pass
