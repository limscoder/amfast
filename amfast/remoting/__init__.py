"""Provides an interface for performing remoting calls."""
import amfast
from amfast import AmFastError, class_def, decoder, encoder

class RemotingError(AmFastError):
    """Remoting related errors."""
    pass

class AsError(RemotingError):
    """Error object that is returned to the client.

    Equivalent to: 'Error' in AS3.
    """

    APPLICATION_ERROR = 5000

    def __init__(self, message='', exc=None):
        self.errorID = self.APPLICATION_ERROR
        if exc is not None:
            self.name = exc.__class__.__name__
            self.message = "%s" % exc
        else:
            self.name = ''
            self.message = message

        RemotingError.__init__(self, self.message)

class_def.assign_attrs(AsError, 'Error', ('errorId', 'name', 'message'), False)

class Service(object):
    """A remoting service is a service that is exposed 
    by a Gateway to AMF clients. 

    attributes:
    ============
     * name - string, service name.
    """

    # Name of special service that handles packet header targets
    PACKET_HEADER_SERVICE = 'PACKET_HEADER_SERVICE'

    # Name of special service that handles message header targets
    MESSAGE_HEADER_SERVICE = 'MESSAGE_HEADER_SERVICE'

    # Name of special service that handles command messages
    COMMAND_SERVICE = 'COMMAND_SERVICE'

    SEPARATOR = '.' # Character used to separate service names and target names

    def __init__(self, name):
        self.name = name
        self._targets = {} # Keeps track of targets internally

    def setTarget(self, target):
        """Add a target to the service."""
        self._targets[target.name] = target

    def getTarget(self, target_name):
        """Get a target from the service by name."""
        return self._targets.get(target_name, None)

    def removeTarget(self, target):
        """Remove a target from the service."""
        if target.name in self._targets:
            del self._targets[target.name]

class Target(object):
    """A remoting target can be invoked by a message.

    attributes:
    ============
     * name - string, name of the target.
    """
    def __init__(self, name):
        self.name = name

    def _invoke_str(self, args):
        return "<targetInvocation target=\"%s\">%s</targetInvocation>" % \
            (self.name, args)

    def invoke(self, request_packet, response_packet, request_msg, response_msg, args):
        """Invoke a target.

        arguments
        ==========
         * request_packet - Packet, Packet that is invoking the target.
         * response_packet - Packet, Packet that is being returned to the client.
         * request_msg - Message, the message that is invoking this target.
             This value will be None if the target is being invoked by a package header.
         * response_msg - Message, the message that is being returned to the client.
             This value will be None if the target is being invoked by a package header.
         * args - list, list of arguments to pass to the callable.
        """
        raise RemotingError("'invoke' must be implemented on a sub-class.")

class CallableTarget(Target):
    """Calls an external callable with the passed arguments when invoked.

    attributes:
    ============
     * name - string, name of the target.
     * callable - callable, a callable that can be invoked.
    """
    def __init__(self, callable, name):
        Target.__init__(self, name)
        self.callable = callable

    def invoke(self, request_packet, response_packet, request_msg, response_msg, args):
        """Calls self.callable and passes *args."""
        if amfast.log_debug:
            amfast.logger.debug(self._invoke_str(args))
        return self.callable(*args)

class ExtCallableTarget(CallableTarget):
    """Calls an external callable with the the same arguments that invoke receives. 

    attributes:
    ============
     * name - string, name of the target.
     * callable - callable, a callable that can be invoked.
    """
    def invoke(self, request_packet, response_packet, request_msg, response_msg, args):
        if amfast.log_debug:
            amfast.logger.debug(self._invoke_str(args))
        return self.callable(request_packet, response_packet, request_msg, response_msg, *args)

class Header(object):
    """A remoting message header.

    attributes:
    ============
     * name - string, header name.
     * required - bool, True if header is required.
     * value - object, header value.
    """
    def __init__(self, name, required=False, value=None):
        self.name = name
        self.required = required
        self.value = value

    def __str__(self):
        return "<header name=\"%s\" required=\"%s\">%s</header>" % (self.name, self.required, self.value)

    def invoke(self, service_mapper, request_packet, response_packet):
        """Invoke an action on this header if one has been mapped."""
        target = service_mapper.packet_header_service.getTarget(self.name)
        if target is not None:
            return target.invoke(request_packet, response_packet, None, None, (self.value,))
        return False

class Message(object):
    """A remoting message body.

    attributes:
    ============
     * target - Target, the target to be invoked.
     * response - string, message id.
     * value - object, message value.
    """

    SUCCESS_TARGET = '/onResult'
    FAILED_TARGET = '/onStatus'
    DEBUG_TARGET = '/onDebugEvents'

    def __init__(self, target=None, response=None, value=None):
        self.target = target
        self.response = response
        self.value = value

    def _isInvokable(self):
        """If True, the message's body can invoke itself."""
        if self.target != 'null':
            return False
        return True
    is_invokable = property(_isInvokable)

    def invoke(self, service_mapper, request_packet, response_packet):
        """Invoke an action on this message and return a response message."""
        try:
            response_msg = self.acknowledge()
            if self.is_invokable:
                self.value[0].invoke(service_mapper, request_packet, response_packet, self, response_msg)
            elif self.target is not None and self.target != '':
                self._invoke(service_mapper, request_packet, response_packet, response_msg)
            else:
                raise RemotingError("Cannot invoke message: '%s'." % self)
        except Exception, exc:
            amfast.log_exc()
            response_msg = self.fail(exc)

        return response_msg

    def _invoke(self, service_mapper, request_packet, response_packet, response_msg):
        """Invoke an action on an AMF0 style message."""
        qualified_name = self.target.split(Service.SEPARATOR)
        if len(qualified_name) < 2:
            raise RemotingError("Target name: '%s' is invalid. Target name must be in the form: 'service%starget'." % \
                (self.target, Service.SEPARATOR))
        target_name = qualified_name.pop()
        service_name = Service.SEPARATOR.join(qualified_name)

        target = service_mapper.getTargetByName(service_name, target_name)
        if target is None:
            raise RemotingError("Target '%s' not found." % self.target)

        response_msg.value = target.invoke(request_packet, response_packet, self, response_msg, self.value)

    def fail(self, exc):
        """Return an error response message."""
        response_target = self.response + self.FAILED_TARGET
        response_message = Message(target=response_target, response='')
        
        if self.is_invokable:
            error_val = self.value[0].fail(exc)
        else:
            error_val = AsError(exc=exc)

        response_message.value = error_val
        return response_message

    def acknowledge(self):
        """Return a successful response message."""
        response_target = self.response + self.SUCCESS_TARGET
        response_message = Message(target=response_target, response='')
        
        if self.is_invokable:
            response_message.value = self.value[0].acknowledge()

        return response_message

    def __str__(self):
        return "<message> <target>%s</target> <response>%s</response> <value>%s</value></message>" % (self.target, self.response, self.value)

class Packet(object):
    """An AMF NetConnection packet that can be passed from client->server or server->client.

    attributes:
    ============
     * version - string, the type of client connected to the server.
     * headers - dict, keys = header names, values = Header objects.
     * messages - list, a list of messages that belong to the packet.
    """

    FLASH_8 = "FLASH_8"
    FLASH_COM = "FLASH_COM"
    FLASH_9 = "FLASH_9"

    def __init__(self, version=None, headers=None, messages=None):
        if version is None:
            version = self.FLASH_8
        self.version = version

        if headers is None:
            headers = []
        self.headers = headers

        if messages is None:
            messages = []
        self.messages = messages

    def __str__(self):
        header_msg = "\n  ".join(["%s" % header for header in self.headers])

        message_msg = "\n  ".join(["%s" % message for message in self.messages])

        return """
<Packet>
 <headers>
  %s
 </headers>

 <messages>
  %s
 </messages>

 <attributes>
  <attr name="version">%s</attr>
 </attributes>
</Packet>
""" % (header_msg, message_msg, self.version)

    def invoke(self, service_mapper):
        """Process this packet and return a response packet."""
        if amfast.log_debug:
            amfast.logger.debug("<requestPacket>%s</requestPacket>" % self)

        response_packet = self.acknowledge()
        try:
            # Invoke any headers
            for header in self.headers:
                header.invoke(service_mapper, self, response_packet)

            # Invoke any messages
            for message in self.messages:
                response_packet.messages.append(message.invoke(service_mapper, self, response_packet))
        except Exception, exc:
            # Fail all messages
            amfast.log_exc()
            response_packet = self.fail(exc)

        if (response_packet.messages is None or len(response_packet.messages) == 0) and \
            (response_packet.headers is None or len(response_packet.headers) == 0):
            # Empty response
            response_packet = None

        if amfast.log_debug:
            amfast.logger.debug("<responsePacket>%s</responsePacket>" % response_packet)

        return response_packet
                
    def fail(self, exc):
        """Return a response Packet with all messages failed."""
        response_packet = self.acknowledge()

        for message in self.messages:
            response_packet.messages.append(message.fail(exc))
        return response_packet

    def acknowledge(self):
        """Create a response to this packet."""
        response_packet = Packet()
        response_packet.version = self.version
        return response_packet

class Gateway(object):
    """An AMF remoting gateway."""
    def __init__(self, service_mapper=None, class_def_mapper=None,
        use_array_collections=False, use_object_proxies=False,
        use_references=True, use_legacy_xml=False, include_private=False):

        self.service_mapper = service_mapper
        if self.service_mapper is None:
            self.service_mapper = ServiceMapper()

        self.class_def_mapper = class_def_mapper
        if self.class_def_mapper is None:
            self.class_def_mapper = class_def.ClassDefMapper()

        self.use_array_collections = use_array_collections
        self.use_object_proxies = use_object_proxies
        self.use_references = use_references
        self.use_legacy_xml = use_legacy_xml
        self.include_private = include_private

    def process_packet(self, raw_packet):
        """Process an incoming packet."""
        if amfast.log_debug:
            amfast.logger.debug("<gateway>Processing incoming packet.</gateway>")

        request_packet = None
        try:
            request_packet = self.decode_packet(raw_packet)
            response_packet = request_packet.invoke(self.service_mapper)
            if response_packet is None:
                return None
            else:
                return self.encode_packet(response_packet)
        except Exception, exc:
            amfast.log_exc()

            if request_packet is not None:
               return self.encode_packet(request_packet.fail(exc))
            else:
                # There isn't much we can do if
                # the request was not decoded correctly.
                raise exc

    def decode_packet(self, raw_packet):
        if amfast.log_debug:
            amfast.logger.debug("<rawRequestPacket>%s</rawRequestPacket>" %
                amfast.format_byte_string(raw_packet))

        return decoder.decode(raw_packet, packet=True,
            class_def_mapper=self.class_def_mapper)

    def encode_packet(self, packet):
        raw_packet = encoder.encode(packet, packet=True, 
            class_def_mapper=self.class_def_mapper,
            use_array_collections=self.use_array_collections,
            use_object_proxies=self.use_object_proxies,
            use_references=self.use_references, use_legacy_xml=self.use_legacy_xml,
            include_private=self.include_private)

        if amfast.log_debug:
            amfast.logger.debug("<rawResponsePacket>%s</rawResponsePacket>" %
                amfast.format_byte_string(raw_packet))

        return raw_packet

class ServiceMapper(object):
    """Maps service to service name.

    attributes
    ===========
    packet_header_service - Service, a special service for AMF packet headers.
    message_header_service - Service, a special service for AMF message headers.
    command_service - Service, a special service for Flex CommandMessages.
    
    When an AMF packet or message is processed, the object checks
    the header_service Service for a target where target.name == header.name
    for each header. If a target is found, the target will be invoked
    before any packet.messages are invoked.

    An example of how to use this functionality is adding a target named 'Credentials'
    to packet_header_service that checks credentials stored in the 'Credentials' header before
    invoking any messages in the packet.
    """

    def __init__(self):
        self._mapped_services = {} # used internally to keep track of Service objects.
        self._mapBuiltIns()

    def _mapBuiltIns(self):
        import amfast.remoting.flex_messages as messaging
        import targets

        # Map built in targets
        self.packet_header_service = Service(Service.PACKET_HEADER_SERVICE)
        self.mapService(self.packet_header_service)
        self.message_header_service = Service(Service.MESSAGE_HEADER_SERVICE)
        self.mapService(self.message_header_service)
        self.command_service = Service(Service.COMMAND_SERVICE)
        self.mapService(self.command_service)

        self.command_service.setTarget(ExtCallableTarget(targets.ro_ping,
            messaging.CommandMessage.CLIENT_PING_OPERATION))

    def mapService(self, service):
        """Maps a service

        arguments
        ==========
         * service - Service, the service to map.
        """
        if service.name in (Service.PACKET_HEADER_SERVICE,
            Service.MESSAGE_HEADER_SERVICE, service.COMMAND_SERVICE):
            if service.name in self._mapped_services:
                raise RemotingError("'%s' name is reserved for internal use." % service.name)

        self._mapped_services[service.name] = service

    def unMapService(self, service):
        """Un-maps a service

        arguments
        ==========
         * service - Service, the service to un-map.
        """
        if service.name in (Service.PACKET_HEADER_SERVICE,
            Service.MESSAGE_HEADER_SERVICE, Service.COMMAND_SERVICE):
            raise RemotingError("'%s' name is reserved for internal use." % service.name)

        if service.name in self._mapped_services:
            del self._mapped_services[service.name]

    def getTargetByName(self, service_name, target_name):
        """Get a Target

        Returns None in Target is not found.

        arguments
        ==========
         * service_name - string, the service name.
         * target_name - string, the target name.
        """
        service = self.getServiceByName(service_name)
        if service is None:
            return None

        return service.getTarget(target_name)

    def getServiceByName(self, service_name):
        """Get a Service

        Returns None in Service is not found.

        arguments
        ==========
         * service_name - string, the service name.
        """
        return self._mapped_services.get(service_name, None)
