import logging
import optparse
import os
import sys

import tornado.httpserver
import tornado.ioloop

import amfast
from amfast.remoting.tornado_channel import TornadoChannelSet, StreamingTornadoChannel


class MainHandler (tornado.web.RequestHandler):
    def get(self):
        self.write("Hello World!")

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

    # If the code is completely asynchronous,
    # you can use the dummy_threading module
    # to avoid RLock overhead.
    import dummy_threading
    amfast.mutex_cls = dummy_threading.RLock

    # Setup ChannelSet
    channel_set = TornadoChannelSet(notify_connections=True)

    # Clients connect every x seconds
    # to polling channels to check for messages.
    # If messages are available, they are
    # returned to the client.
    streaming_channel = StreamingTornadoChannel('amf')
    channel_set.mapChannel(streaming_channel)

    static_path = os.path.join(os.path.dirname(__file__), '..', 'flex', 'deploy')

    application = tornado.web.Application([
        (r"/amf", streaming_channel.request_handler),
    ], static_path=static_path)

    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(int(options.port))
    tornado.ioloop.IOLoop.instance().start()
