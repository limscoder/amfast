"""An example server using the Twisted framework.
To run, execute the following command:
    twistd -noy twisted_server.tac
"""
from twisted.application import service, strports
from twisted.web import static, server, resource, vhost

import amfast
from amfast.remoting.gateway import Gateway, Channel

import utils

class AmfChannel(resource.Resource):
    """Controller class that directs requests to the Gateway."""

    def __init__(self, gateway):
        resource.Resource.__init__(self)
        self.channel = Channel('amfast-channel', gateway)
        
        # Set this to True to see AmFast
        # debugging info
        amfast.log_debug = False

    def render_POST(self, request):
        if request.content:
            return self.channel.invoke(request.content.getvalue())
        else:
            raise Exception("No content")

# Setup domain 
root = vhost.NameVirtualHost()
root.default = static.File("../flex/deploy")
domain = "localhost"
root.addHost(domain, static.File("../flex/deploy"))

# Setup Gateway
gateway = Gateway()
utils.setup_gateway(gateway)

# Setup channels
root.putChild('amf', AmfChannel(gateway))

# Setup server
port = 8000
application = service.Application('AmFast Example')
server = strports.service('tcp:%s' % port, server.Site(root))
server.setServiceParent(application)

print "serving on %s:%s" % (domain, port)
print "Press ctrl-c to halt."
