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

# Setup ChannelSet
channel_set = ChannelSet()
rpc_channel = TwistedChannel('rpc')
channel_set.mapChannel(rpc_channel)
utils.setup_channel_set(channel_set)

# Setup domain 
root = vhost.NameVirtualHost()
root.default = static.File("../flex/deploy")
domain = "localhost"
root.addHost(domain, static.File("../flex/deploy"))

# Setup HTTP channels
root.putChild('amf', rpc_channel)

# Setup server
application = service.Application('AmFast Example')

# HTTP server
http_port = 8000
http_server = strports.service('tcp:%s' % http_port, server.Site(root))
http_server.setServiceParent(application)

print "serving on %s:%s" % (domain, http_port)
print "Press ctrl-c to halt."
