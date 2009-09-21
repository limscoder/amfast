import logging
import optparse
import os
import sys

import tornado.httpserver
import tornado.ioloop

import amfast
from amfast.remoting.tornado_channel import TornadoChannelSet, TornadoChannel


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
    polling_channel = TornadoChannel('amf')
    channel_set.mapChannel(polling_channel)

    # Long-poll channels do not return
    # a response to the client until
    # a message is available, or channel.max_interval
    # is reached.
    long_poll_channel = TornadoChannel('longPoll', wait_interval=90)
    channel_set.mapChannel(long_poll_channel)

    static_path = os.path.join(os.path.dirname(__file__), '..', 'flex', 'deploy')

    application = tornado.web.Application([
        (r"/amf", polling_channel.request_handler),
        (r"/longPoll", long_poll_channel.request_handler),
    ], static_path=static_path)

    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(int(options.port))
    tornado.ioloop.IOLoop.instance().start()
