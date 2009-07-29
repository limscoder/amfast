"""An example server using the Twisted framework.

To run, execute the following command:
    twistd -noy twisted_server.tac
"""
import logging
import sys

from twisted.application import service, strports
from twisted.web import static, server, resource, vhost

import amfast
from amfast.remoting.twisted_channel import TwistedChannelSet, StreamingTwistedChannel

# Uncomment this like to log debug messages
#amfast.log_debug = True

# Send log messages to STDOUT
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
amfast.logger.addHandler(handler)

# Setup domain 
root = vhost.NameVirtualHost()
root.default = static.File("../flex/deploy")
domain = "localhost"
root.addHost(domain, static.File("../flex/deploy"))

# If the code is completely asynchronous, 
# you can use the dummy_threading module
# to avoid RLock overhead.
import dummy_threading
amfast.mutex_cls = dummy_threading.RLock

# Setup ChannelSet
channel_set = TwistedChannelSet(notify_connections=True)
stream_channel = StreamingTwistedChannel('streaming-channel')
channel_set.mapChannel(stream_channel)

# Setup channels
root.putChild('amf', stream_channel)

# Setup server
port = 8000
application = service.Application('AmFast Example')
server = strports.service('tcp:%s' % port, server.Site(root))
server.setServiceParent(application)

print "serving on %s:%s" % (domain, port)
print "Press ctrl-c to halt."
