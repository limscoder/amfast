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
from amfast.remoting.twisted_channel import TwistedChannel

# Uncomment this to see debug messages
#amfast.log_debug = True
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

# Clients connect every x seconds
# to polling channels to check for messages.
# If messages are available, they are
# returned to the client.
polling_channel = TwistedChannel('amf-polling-channel')
channel_set.mapChannel(polling_channel)

# Long-poll channels do not return
# a response to the client until
# a message is available, or channel.max_interval
# is reached.
long_poll_channel = TwistedChannel('long-poll-channel', wait_interval=-1)
channel_set.mapChannel(long_poll_channel)

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
