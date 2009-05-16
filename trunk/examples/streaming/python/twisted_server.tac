"""An example server using the Twisted framework.

To run, execute the following command:
    twistd -noy twisted_server.tac
"""
import logging
import sys

from twisted.application import service, strports
from twisted.web import static, server, resource, vhost

import amfast
from amfast.remoting.channel import ChannelSet
from amfast.remoting.twisted_channel import StreamingTwistedChannel

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

# Setup ChannelSet
channel_set = ChannelSet()
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
