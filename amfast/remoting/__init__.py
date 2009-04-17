"""Provides an interface for performing remoting calls."""

import threading

import amfast
from amfast import AmFastError, class_def, decoder, encoder
from amfast.class_def.as_types import AsError

class RemotingError(AmFastError):
    """Remoting related errors."""
    pass

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

    # Name of special service that handles targets without a service prefix
    DEFAULT_SERVICE = 'DEFAULT_SERVICE'

    SEPARATOR = '.' # Character used to separate service names and target names

    def __init__(self, name):
        self.name = name

        self._lock = threading.RLock()
        self._targets = {} # Keeps track of targets internally

    def mapTarget(self, target):
        """Add a target to the service."""
        self._lock.acquire()
        try:
            self._targets[target.name] = target
        finally:
            self._lock.release()

    def unMapTarget(self, target):
        """Remove a target from the service."""
        self._lock.acquire()
        try:
            if target.name in self._targets:
                del self._targets[target.name]
        finally:
            self._lock.release()

    def getTargetByName(self, target_name):
        """Get a target from the service by name."""
        self._lock.acquire()
        try:
            target = self._targets.get(target_name, None)
        finally:
            self._lock.release()
        return target

class Target(object):
    """A remoting target can be invoked by a message.

    attributes:
    ============
     * name - string, name of the target.
    """
    def __init__(self, name):
        self.name = name

    def _invokeStr(self, args):
        return "<targetInvocation target=\"%s\">%s</targetInvocation>" % \
            (self.name, args)

    def invoke(self, packet, msg, args):
        """Invoke a target.

        arguments
        ==========
         * packet - Packet, Packet that is invoking the target.
         * msg - Message, the message that is invoking this target.
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

    def invoke(self, packet, msg, args):
        """Calls self.callable and passes *args."""
        if amfast.log_debug:
            amfast.logger.debug(self._invokeStr(args))
        return self.callable(*args)

class ExtCallableTarget(CallableTarget):
    """Calls an external callable with the the same arguments that invoke receives. 

    attributes:
    ============
     * name - string, name of the target.
     * callable - callable, a callable that can be invoked.
    """
    def invoke(self, packet, msg, args):
        if amfast.log_debug:
            amfast.logger.debug(self._invokeStr(args))
        return self.callable(packet, msg, *args)

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

    def invoke(self, request):
        """Invoke an action on this header if one has been mapped."""
        target = request.gateway.service_mapper.packet_header_service.getTargetByName(self.name)
        if target is not None:
            return target.invoke(request, None, (self.value,))
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

    def invoke(self, request):
        """Invoke an action on this message and return a response message."""
        try:
            self.response_msg = self.acknowledge()
            if self.is_invokable:
                self.value[0].invoke(request, self)
            elif self.target is not None and self.target != '':
                self._invoke(request)
            else:
                raise RemotingError("Cannot invoke message: '%s'." % self)
        except Exception, exc:
            amfast.log_exc()
            self.response_msg = self.fail(exc)

        return self.response_msg

    def _invoke(self, request):
        """Invoke an action on an AMF0 style message."""
        qualified_name = self.target.split(Service.SEPARATOR)
        if len(qualified_name) < 2:
            target_name = self.target
            service_name = Service.DEFAULT_SERVICE
        else:
            target_name = qualified_name.pop()
            service_name = Service.SEPARATOR.join(qualified_name)

        target = request.gateway.service_mapper.getTargetByName(service_name, target_name)
        if target is None:
            raise RemotingError("Target '%s' not found." % self.target)

        self.response_msg.value = target.invoke(request, self, self.value)

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

    def _getAmf3(self):
        if self.version == self.FLASH_9:
            return True
        return False
    is_amf3 = property(_getAmf3)

    def invoke(self):
        """Process this packet and return a response packet."""
        if amfast.log_debug:
            amfast.logger.debug("<requestPacket>%s</requestPacket>" % self)

        self.response = self.acknowledge()
        try:
            # Invoke any headers
            for header in self.headers:
                header.invoke(self)

            # Invoke any messages
            for message in self.messages:
                self.response.messages.append(message.invoke(self))
        except Exception, exc:
            # Fail all messages
            amfast.log_exc()
            self.response = self.fail(exc)

        if amfast.log_debug:
            amfast.logger.debug("<responsePacket>%s</responsePacket>" % self.response)

        return self.response

    def fail(self, exc):
        """Return a response Packet with all messages failed."""
        response = self.acknowledge()

        for message in self.messages:
            response.messages.append(message.fail(exc))
        return response

    def acknowledge(self):
        """Create a response to this packet."""
        response = Packet()
        response.version = self.version
        return response

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

class ServiceMapper(object):
    """Maps service to service name.

    attributes
    ===========
    packet_header_service - Service, a special service for AMF packet headers.
    message_header_service - Service, a special service for AMF message headers.
    command_service - Service, a special service for Flex CommandMessages.
    default_service - Service, a special service for targets that don't have service specifiers.
    
    When an AMF packet or message is processed, the object checks
    the header_service Service for a target where target.name == header.name
    for each header. If a target is found, the target will be invoked
    before any packet.messages are invoked.

    An example of how to use this functionality is adding a target named 'Credentials'
    to packet_header_service that checks credentials stored in the 'Credentials' header before
    invoking any messages in the packet.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._services = {} # used internally to keep track of Service objects.
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
        self.default_service = Service(Service.DEFAULT_SERVICE)
        self.mapService(self.default_service)

        # CommandMessages
        self.command_service.mapTarget(ExtCallableTarget(targets.client_ping,
            messaging.CommandMessage.CLIENT_PING_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.subscribe_operation,
            messaging.CommandMessage.SUBSCRIBE_OPERATION))

    def mapService(self, service):
        """Maps a service

        arguments
        ==========
         * service - Service, the service to map.
        """
        self._lock.acquire()
        try:
            self._services[service.name] = service
        finally:
            self._lock.release()

    def unMapService(self, service):
        """Un-maps a service

        arguments
        ==========
         * service - Service, the service to un-map.
        """
        self._lock.acquire()
        try:
            if service.name in self._services:
                del self._services[service.name]
        finally:
            self._lock.release()

    def getTargetByName(self, service_name, target_name):
        """Get a Target

        Returns None in Target is not found.

        arguments
        ==========
         * service_name - string, the service name.
         * target_name - string, the target name.
        """
        self._lock.acquire()
        try:
            service = self.getServiceByName(service_name)
            if service is None:
                target = None
            else:
                target = service.getTargetByName(target_name)
        finally:
            self._lock.release()

        return target

    def getServiceByName(self, service_name):
        """Get a Service

        Returns None in Service is not found.

        arguments
        ==========
         * service_name - string, the service name.
        """
        self._lock.acquire()
        try:
            service = self._services.get(service_name, None)
        finally:
            self._lock.release()
        return service
