# Messaging Server #



## Overview ##

  * ChannelSet objects route request messages and dispatch response messages.
  * Each ChannelSet contains one or more Channel objects. Channels handle the technical details of sending and receiving messages.
  * AmFast includes built-in Channels for [CherryPy](http://cherrypy.org), [Twisted Web](http://twistedmatrix.com/trac/), [Google App Engine](http://code.google.com/appengine/), [Django](http://www.djangoproject.com/,), and plain WSGI.

```
from amfast.remoting.wsgi_channel import WsgiChannelSet, WsgiChannel

# Each ChannelSet contains one or more Channels.
# Channels handle the actual receiving and sending of messages.
channel_set = WsgiChannelSet()

# Create a WsgiChannel, which uses
# WSGI to handle messages.
channel_set.mapChannel(WsgiChannel('channel-name'))

# Serve the WSGI channel
server = simple_server((domain, port), simple_server.WSGIRequestHandler)
server.set_app(channel_set)
server.serve_forever()

# Our messaging server is up and running!
```


---


## Mapping RPC Destinations ##
  * Target objects map callables to RPC destinations.
  * Service objects are collections of Targets.
  * ServiceMapper objects are collections of services.
  * Each ChannelSet object contains a ServiceMapper that it uses to route RPC messages.

```
from amfast import remoting

# This function will be exposed to remote invocation.
# The arguments are passed from the client.
def remote_function(arg1, arg2):
    print "%s:%s" % (arg1, arg2)

# A CallableTarget contains a callable
# that gets invoked when a request message
# is received.
target = remoting.CallableTarget(remote_function, 'exposed_method_name')

# A Service object is a collection of Targets.
service = remoting.Service('exposed_service_name')

# Add a target to a service.
service.mapTarget(target)

# A ServiceMapper object keeps track
# of all exposed services and targets.
service_mapper = remoting.ServiceMapper()

# Add a service to a ServiceMapper.
service_mapper.mapService(service)

# Expose the ServiceMapper's Services
channel_set.service_mapper = service_mapper

# The mapped target can be accessed from a client
# with a NetConnection or RemoteObject request to:
# 'exposed_service_name.exposed_method_name'
```

### Exposing AMF Packet and Message to Targets ###
  * AMF Packet and AMF Message objects can be exposed to Targets using the ExtCallableTargetClass.
  * This is useful if you need to access Packet or FlexMessage headers.

```
from amfast import remoting

# This function will be exposed.
# In addition to any arguments supplied
# by the client, the AMF Packet and Message
# objects that invoked the Target are passed.
def remote_function(packet, message, arg1, arg2):
    my_flex_message = message.body[0]
    print "%s:%s" % (arg1, arg2)

# Use ExtCallableTarget to expose
# the request Packet and Message to
# the callable.
target = remoting.ExtCallableTarget(remoting_function, 'ext_exposed_method_name')
```

### Mapping AMF Packet Headers to Targets ###
  * AMF Packet Headers can be mapped to Targets that get invoked whenever a request Packet containing the Header is received.

```
from amfast import remoting

# This function will be invoked when
# the header it is mapped to is present
# in an AMF request Packet.
# The Header object is passed to the function.
def function_exposed_to_header(header_val):
    print header_val

# The target's name must be the name of the header.
target = remoting.CallableTarget(function_exposed_to_header, 'header_name')

# Use the special attribute
# 'packet_header_service' to map
# a header Target.
service_mapper.packet_header_service.mapTarget(target)
```

### Mapping CommandMessages to Targets ###
  * CommandMessages can be mapped to Targets by mapping the CommandMessage's operation number.

```
from amfast import remoting

# This function will be invoked when
# a CommandMessage is received.
# The CommandMessage object body will be passed.
def function_exposed_to_command(command_body):
    print command_body

# Use the CommandMessage's
# 'operation' value to create
# a target.
target = remoting.CallableTarget(function_exposed_to_command, OPERATION_NUMBER)

# Use the special attribute
# 'command_service' to map the target.
service_mapper.command_service.mapTarget(target)
```


---


### Storing Session Data ###
  * Use Connection objects to store session data.

#### RemoteObject Session Data ####
  * Connection objects are created automatically for RemoteObject Clients.

```
# Use ExtCallableTarget to expose Packet and Message objects.
def remote_function(packet, message, *args):
    # Get a Connection object from a Flex message.
    my_flex_message = message.body[0]
    connection = my_flex_message.connection

    connection.setSessionAttr('new_attr_name', 'value')
    val = connection.getSessionAttr('new_attr_nam')
```

#### NetConnection Session Data ####
  * You can also store session data for NetConnection clients, but you will have to manually create the Connection and pass the connection id.

```
# To store session data with NetConnection,
# the Connection object will need to be created manually,
# and the connection id will have to be passed as an argument
# or as a Packet header.
def remote_function(packet, message, connection_id):
    try:
        connection = packet.channel.channel_set.getConnection(connection_id)
    except amfast.remoting.channel.NotConnectedError:
        connection_id = packet.channel.channel_set.generateId()
        connection = packet.channel.connect(connection_id)
```

#### Persistent Connection and Subscription Data ####
  * By default ChannelSets use the MemoryConnectionManager and MemorySubscriptionManager classes to store connection and message information in memory.
  * Use GaeConnectionManager and GaeSubscriptionManager to store data in Google DataStore.
  * Use SaConnectionManager and SaSubscriptionManager to store data in a SQL database.
  * Use MemcacheConnectionManager and MemcacheSubscriptionManager to store data in a Memcache instance.

```
from amfast.remoting.memcache_subscription_manager import MemcacheSubscriptionManager
from amfast.remoting.memcache_connection_manager import MemcacheConnectionManager
from amfast.remoting.wsgi_channel import WsgiChannelSet

# Specify the connection_manager and/or
# the subscription_manager
# arguments when instantiating a ChannelSet to
# customize connection and message storage.
channel_set = WsgiChannelSet(connection_manager=MemcacheConnectionManager(),
    subscription_manager=MemcacheSubscriptionManager())
```


---


## Producer/Consumer Messaging ##
  * Each ChannelSet object handles Flex message subscriptions and publishing for all of its Channels.
  * In the examples below, the body of the message is a string, but the body may be any Python object.

```
from amfast.remoting import flex_messages

# Create a Flex message to publish.
msg = flex_messages.AsyncMessage(headers=None,
    body="Hello World", destination="topic-name")

channel_set.publishMessage(msg)

# ChannelSet also has a 'publishObject'
# method which is a convenience method to
# automatically create a new AsynceMessage
# to publish.
channel_set.publishObject("Hello World", "topic-name",
    sub_topic="sub-topic-name", headers=None, ttl=30000)
```


---


## Authentication ##
  * Authentication can be used with both NetConnection and RemoteObject.
  * Targets and MessageAgents can be secured.

```
from amfast.remoting.channel import ChannelSet

# Add a login method to a ChannelSet
# to enable authentication.
#
# The method should accept user and password
# arguments. It should return True on login,
# and raise a amfast.remoting.channel.SecurityError
# on failure.
class AuthChannelSet(ChannelSet):
    def login(self, user, password):
        if user == 'correct' and 'pass' == 'correct':
            return True

        raise amfast.remoting.channel.SecurityError('Invalid credentials.')

channel_set = AuthChannelSet()

# Set the 'secure' attribute to True
# to protect a Target.
#
# This will stop unauthenticated users
# from invoking a Target.
target.secure = True

# Set the 'secure' attribute of the
# SubscriptionManager to True
# to protect Producer/Consumer messaging.
#
# This will stop un-authenticated
# users from publishing or subscribing
# to topics.
channel_set.subscription_manager.secure = True
```


---


## Configurable Endpoints ##
  * Channel objects use Endpoint objects to encode and decode the messages they receive.
  * Object serialization and de-serialization is customized on a per-Channel basis by configuring the Channel's endpoints.

### AmfEndpoint ###
  * AmfEndpoint uses AmFast's built-in AMF encoder/decoder.
  * See [EncodeAndDecode](EncodeAndDecode#Custom_Type_Maps.md) page for information about configuring Encoder and Decoder objects and how to map custom types.

```
# AmFast's default Endpoint
# encodes/decodes AMF packets
# with a C-extension, so it is very fast.
from amfast.remoting.endpoint import AmfEndpoint

# The AmfEndpoint uses 
# Encoder and Decoder objects.
# to customize how objects
# are serialized/deserialized.
from amfast.encoder import Encoder
from amfast.decoder import Decoder

# This channel will encode and decode messages
# with an AmfEndpoint.
channel.endpoint = AmfEndpoint(encoder=Encoder(), decoder=Decoder()))
```

### PyAmfEndpoint ###
  * Use the PyAmfEndpoint for a pure-Python encoder/decoder.
  * See [PyAmf](http://pyamf.org) project for details about configuring the PyAmf encoder/decoder.
  * See [EncodeAndDecode](EncodeAndDecode#Custom_Type_Maps.md) page for information about how to map custom types with AmFast.

```
# Use the PyAmfEndpoint
# for a pure-Python alternative.
from amfast.remoting.pyamf_endpoint import PyAmfEndpoint

channel.endpoint = PyAmfEndpoint()

# When using the PyAmfEndpoint,
# custom type mapping can be configured
# either through AmFast, or through PyAmf.

# Configure type mapping with AmFast
class_mapper = ClassDefMapper()

#... map classes ...#

# Use pyamf_converter to automatically map classes
# from a ClassDefMapper with PyAmf.
import amfast.remoting.pyamf_converter as pyamf_converter
pyamf_converter.register_class_mapper(class_mapper)

# Configure type mapping directly with PyAmf.
# Use the standard PyAmf way of mapping classes.
pyamf.register_class(klass, 'alias', ....)
```