"""An example server using the Twisted framework.

To run, execute the following command:
    twistd -noy twisted_server.tac
"""
from twisted.application import service, strports
from twisted.web import static, server, resource, vhost

import amfast
from amfast.remoting.twisted_channel import TwistedChannelSet, TwistedChannel

import utils

# Setup domain 
root = vhost.NameVirtualHost()
root.default = static.File("../flex/deploy")
domain = "localhost"
root.addHost(domain, static.File("../flex/deploy"))

# Setup ChannelSet
channel_set = TwistedChannelSet()
rpc_channel = TwistedChannel('rpc')
channel_set.mapChannel(rpc_channel)
utils.setup_channel_set(channel_set)

# Setup channels
root.putChild('amf', rpc_channel)

# Setup server
port = 8000
application = service.Application('AmFast Example')
server = strports.service('tcp:%s' % port, server.Site(root))
server.setServiceParent(application)

print "serving on %s:%s" % (domain, port)
print "Press ctrl-c to halt."
