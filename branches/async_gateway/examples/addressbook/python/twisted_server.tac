"""An example server using the Twisted framework.
To run, execute the following command:
    twistd -noy twisted_server.tac
"""
from twisted.application import service, strports
from twisted.web import static, server, resource, vhost

import amfast

import utils

class AmfGateway(resource.Resource):
    """Controller class that directs requests to the Gateway."""

    def __init__(self):
        resource.Resource.__init__(self)
        self.gateway = amfast.remoting.Gateway()
        utils.setup_gateway(self.gateway)
        
        # Set this to True to see AmFast
        # debugging info
        amfast.log_debug = False

    def render_POST(self, request):
        if request.content:
            return self.gateway.process_packet(request.content.getvalue())
        else:
            raise Exception("No content")

# Setup domain 
root = vhost.NameVirtualHost()
root.default = static.File("../flex/deploy")
domain = "localhost"
root.addHost(domain, static.File("../flex/deploy"))

# Mount urls
root.putChild('amfGateway', AmfGateway())

# Setup server
port = 8000
application = service.Application('AmFast Example')
server = strports.service('tcp:%s' % port, server.Site(root))
server.setServiceParent(application)

print "serving on %s:%s" % (domain, port)
print "Press ctrl-c to halt."
