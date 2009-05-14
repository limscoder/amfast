"""An example server using the Twisted framework.

To run, execute the following command:
    twistd -noy twisted_server.tac
"""
from twisted.application import service, strports
from twisted.web import static, server, resource, vhost

import amfast
from amfast.remoting.channel import ChannelSet
from amfast.remoting.twisted_channel import TwistedChannel

import utils

# Uncomment this to see debug messages
#amfast.log_debug = True

# Setup domain 
root = vhost.NameVirtualHost()
root.default = static.File("../flex/deploy")
domain = "localhost"
root.addHost(domain, static.File("../flex/deploy"))

# Setup ChannelSet
channel_set = ChannelSet()
polling_channel = TwistedChannel('amf-polling-channel')
channel_set.mapChannel(polling_channel)
long_poll_channel = TwistedChannel('long-poll-channel', wait_interval=-1)
channel_set.mapChannel(long_poll_channel)
utils.setup_channel_set(channel_set)

# Setup channels
root.putChild('amf', polling_channel)
root.putChild('longPoll', long_poll_channel)

# Setup server
port = 8000
application = service.Application('AmFast Example')
server = strports.service('tcp:%s' % port, server.Site(root))
server.setServiceParent(application)

print "serving on %s:%s" % (domain, port)
print "Press ctrl-c to halt."
