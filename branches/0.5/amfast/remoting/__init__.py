"""Provides an interface for performing remoting calls."""

import threading

import amfast
from amfast import AmFastError, class_def
from amfast.class_def.as_types import AsError

class RemotingError(AmFastError):
    """Remoting related errors."""
    pass

class Service(object):
    """A remoting service is a service that is exposed 
    by an amfast.remoting.channel.Channel to AMF clients. 

    attributes:
    ============
     * name - string, service name.
    """

    # Name of special service that handles packet header targets
    PACKET_HEADER_SERVICE = 'PACKET_HEADER_SERVICE'

    # Name of special service that handles command messages
    COMMAND_SERVICE = 'COMMAND_SERVICE'

    # Name of special service that handles targets without a service prefix
    DEFAULT_SERVICE = 'DEFAULT_SERVICE'

    SEPARATOR = '.' # Character used to separate service names and target names

    def __init__(self, name):
        self.name = name

        self._lock = threading.RLock()
        self._targets = {} # Keeps track of targets internally

    def __iter__(self):
        return self._targets.itervalues()

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

    def getTarget(self, target_name):
        """Get a target from the service by name."""
        self._lock.acquire()
        try:
            target = self._targets.get(target_name, None)
        finally:
            self._lock.release()
        return target

class Target(object):
    """A remoting target can be invoked by an RPC message received from a client.

    attributes:
    ============
     * name - string, name of the target.
     * secure - boolean, True to require login.
    """
    def __init__(self, name, secure=False):
        self.name = name
        self.secure = secure

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
     * secure - boolean, True to require login.
     * callable - callable, a callable that can be invoked.
    """
    def __init__(self, callable, name, secure=False):
        Target.__init__(self, name, secure)
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
     * secure - boolean, True to require login.
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
        target = request.channel.channel_set.service_mapper.\
            packet_header_service.getTarget(self.name)
        if target is not None:
            return target.invoke(request, None, (self.value,))
        return False

class Message(object):
    """A remoting message body.

    attributes:
    ============
     * target - Target, the target to be invoked.
     * response - string, message id.
     * body - object, message body.
    """

    SUCCESS_TARGET = '/onResult'
    FAILED_TARGET = '/onStatus'
    DEBUG_TARGET = '/onDebugEvents'

    def __init__(self, target=None, response=None, body=None):
        self.target = target
        self.response = response
        self.body = body

    def _isInvokable(self):
        """If True, the message's body can invoke itself."""
        if self.target == 'null':
            return True
        return False
    is_invokable = property(_isInvokable)

    def _isFlexMsg(self):
        """If True, the message's body is a Flex message."""
        return hasattr(self.body, 'FLEX_CLIENT_ID_HEADER')
    is_flex_msg = property(_isFlexMsg)

    def invoke(self, request):
        """Invoke an action on an RPC message and return a response message."""
        try:
            self.response_msg = self.acknowledge(request)
            if self.is_invokable:
                self.body[0].invoke(request, self)
            elif self.target is not None and self.target != '':
                self._invoke(request)
            else:
                raise RemotingError("Cannot invoke message: '%s'." % self)
        except Exception, exc:
            amfast.log_exc(exc)
            self.response_msg = self.fail(request, exc)

        return self.response_msg

    def _invoke(self, request):
        """Invoke an action on an AMF0 style RPC message."""
        qualified_name = self.target.split(Service.SEPARATOR)
        if len(qualified_name) < 2:
            target_name = self.target
            service_name = Service.DEFAULT_SERVICE
        else:
            target_name = qualified_name.pop()
            service_name = Service.SEPARATOR.join(qualified_name)

        target = request.channel.channel_set.service_mapper.getTarget(service_name, target_name)
        if target is None:
            raise RemotingError("Target '%s' not found." % self.target)

        if target.secure is True:
            # Make sure user is authenticated
            if not hasattr(request, '_authenticated'):
                raise RemotingError('Target requires authentication.');

        self.response_msg.body = target.invoke(request, self, self.body)

    def fail(self, request, exc):
        """Return an error response message."""
        response_target = self.response + self.FAILED_TARGET
        response_message = Message(target=response_target, response='')
        
        if self.is_invokable:
            error_val = self.body[0].fail(request, self, exc)
        else:
            error_val = AsError(exc=exc)

        response_message.body = error_val
        return response_message

    def convertFail(self, exc):
        """Convert a successful message into a failure."""
        self.target.replace(self.SUCCESS_TARGET, self.FAILED_TARGET)
        
        if self.is_flex_msg:
            self.body = self.body.convertFail(exc=exc)
        else:
            self.body = AsError(exc=exc)

    def acknowledge(self, request):
        """Return a successful response message to acknowledge an RPC message."""
        response_target = self.response + self.SUCCESS_TARGET
        response_message = Message(target=response_target, response='')
        
        if self.is_invokable:
            response_message.body = self.body[0].acknowledge(request, self)

        return response_message

    def __str__(self):
        return "<message> <target>%s</target> <response>%s</response> <body>%s</body></message>" % (self.target, self.response, self.body)

class Packet(object):
    """An AMF NetConnection packet that can be passed from client->server or server->client.

    attributes:
    ============
     * client_type - string, the type of client connected to the server.
     * headers - dict, keys = header names, values = Header objects.
     * messages - list, a list of messages that belong to the packet.
    """

    FLASH_8 = 0x00
    FLASH_COM = 0x01
    FLASH_9 = 0x03

    def __init__(self, client_type=None, headers=None, messages=None):
        if client_type is None:
            client_type = self.FLASH_8
        self.client_type = client_type 

        if headers is None:
            headers = []
        self.headers = headers

        if messages is None:
            messages = []
        self.messages = messages

    def _getAmf3(self):
        if self.client_type == self.FLASH_9:
            return True
        return False
    is_amf3 = property(_getAmf3)

    def invoke(self):
        """Process an RPC packet and return a response packet."""
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
            amfast.log_exc(exc)
            self.response = self.fail(exc)

        if amfast.log_debug:
            amfast.logger.debug("<responsePacket>%s</responsePacket>" % self.response)

        return self.response

    def fail(self, exc):
        """Return a response Packet with all messages failed."""
        response = self.acknowledge()

        for message in self.messages:
            response.messages.append(message.fail(self, exc))
        return response

    def acknowledge(self):
        """Create a response to this packet."""
        response = Packet()
        response.client_type = self.client_type
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
  <attr name="client_type">%s</attr>
 </attributes>
</Packet>
""" % (header_msg, message_msg, self.client_type)

class ServiceMapper(object):
    """Maps service to service name.

    attributes
    ===========
     * packet_header_service - Service, a special service for AMF packet headers.
     * message_header_service - Service, a special service for AMF message headers.
     * command_service - Service, a special service for Flex CommandMessages.
     * default_service - Service, a special service for targets that don't have service specifiers.
    
    When an AMF packet or message is processed, the object checks
    the header_service Service for a target where target.name == header.name
    for each header. If a target is found, the target will be invoked
    before any packet.messages are invoked.

    An example of how to use this functionality is adding a target named 'Credentials'
    to packet_header_service that checks credentials stored in the 'Credentials' header before
    invoking any messages in the packet.
    """

    def __init__(self):
        self._services = {} # used internally to keep track of Service objects.
        self._mapBuiltIns()
        self._lock = threading.RLock()

    def __iter__(self):
        return self._services.itervalues()

    def _mapBuiltIns(self):
        """Map default Targets required for Authentication and FlexMessaging.

        Users can override the defaults, by remapping their own targets.
        """ 
        import amfast.remoting.flex_messages as messaging
        import targets

        # Map built in targets
        self.packet_header_service = Service(Service.PACKET_HEADER_SERVICE)
        self.mapService(self.packet_header_service)
        self.command_service = Service(Service.COMMAND_SERVICE)
        self.mapService(self.command_service)
        self.default_service = Service(Service.DEFAULT_SERVICE)
        self.mapService(self.default_service)

        # NetConnection authentication
        self.packet_header_service.mapTarget(ExtCallableTarget(targets.nc_auth,
            'Credentials'))

        # CommandMessages
        self.command_service.mapTarget(ExtCallableTarget(targets.client_ping,
            messaging.CommandMessage.CLIENT_PING_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.login_operation,
            messaging.CommandMessage.LOGIN_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.logout_operation,
            messaging.CommandMessage.LOGOUT_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.poll_operation,
            messaging.CommandMessage.POLL_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.subscribe_operation,
            messaging.CommandMessage.SUBSCRIBE_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.unsubscribe_operation,
            messaging.CommandMessage.UNSUBSCRIBE_OPERATION))
        self.command_service.mapTarget(ExtCallableTarget(targets.disconnect_operation,
            messaging.CommandMessage.DISCONNECT_OPERATION))

    def mapService(self, service):
        """Maps a service

        arguments
        ==========
         * service - Service, the service to map.
        """
        self._services[service.name] = service

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

    def getTarget(self, service_name, target_name):
        """Get a Target

        Returns None in Target is not found.

        arguments
        ==========
         * service_name - string, the service name.
         * target_name - string, the target name.
        """
        self._lock.acquire()
        try:
            service = self.getService(service_name)
            if service is None:
                target = None
            else:
                target = service.getTarget(target_name)
        finally:
            self._lock.release()

        return target

    def getService(self, service_name):
        """Get a Service

        Returns None in Service is not found.

        arguments
        ==========
         * service_name - string, the service name.
        """
        return self._services.get(service_name, None)
