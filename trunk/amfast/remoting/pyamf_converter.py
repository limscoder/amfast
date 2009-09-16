"""Functions to convert objects between PyAmf and AmFast."""

import pyamf
import pyamf.remoting as pyamf_remoting
import pyamf.flex.messaging as pyamf_messaging

import amfast
import amfast.class_def as class_def
import amfast.remoting as amfast_remoting
import amfast.remoting.flex_messages as amfast_messaging

class PyAmfConversionError(amfast.AmFastError):
    """Raised when conversion to/from PyAmf datatype fails."""
    pass

class PyAmfVersionError(PyAmfConversionError):
    """Raised when installed version of PyAmf is not compatible."""

if pyamf.__version__[1] < 4:
    raise PyAmfVersionError('PyAmf version is not compatible.')

#---------- FROM PyAmf TO AmFast -----------#
def packet_to_amfast(pyamf_packet):
    """Converts a PyAmf Envelope to an AmFast Packet.

    arguments:
    ===========
     * pyamf_packet - pyamf.remoting.Envelope.

    Returns amfast.remoting.Packet
    """
    if pyamf_packet.clientType == pyamf.ClientTypes.Flash6:
        client_type = amfast_remoting.Packet.FLASH_8
    elif pyamf_packet.clientType == pyamf.ClientTypes.FlashCom:
        client_type = amfast_remoting.Packet.FLASH_COM
    elif pyamf_packet.clientType == pyamf.ClientTypes.Flash9:
        client_type = amfast_remoting.Packet.FLASH_9
    else:
        clientType = amfast_remoting.Packet.FLASH_8 

    headers = [amfast_remoting.Header(name,
        required=pyamf_packet.headers.is_required(name), value=header) \
        for name, header in pyamf_packet.headers]

    messages = [message_to_amfast(name, body) for name, body in pyamf_packet.bodies]

    return amfast_remoting.Packet(client_type=client_type, headers=headers, messages=messages)

def message_to_amfast(name, msg):
    """Converts a PyAmf Request to an AmFast Message

    arguments:
    ===========
     * name - string, response
     * msg - pyamf.remoting.Request

    Returns amfast.remoting.Message
    """ 
    if hasattr(msg, 'target'):
        target = msg.target
    else:
        target = ''

    if hasattr(msg, 'status'):
        response = name + msg.status
    else:
        response = name

    return amfast_remoting.Message(target=target, response=response, body=msg.body)

#--------- FROM AmFast to PyAmf -----------#
def dummy_callable(obj):
    """A callable that you probably shouldn't be using :)"""
    return []

def class_def_alias(class_def):
    """Create a pyamf.ClassAlias object that uses a ClassDef for the actual operations.

    arguments:
    ==========
     * class_def - amfast.class_def.ClassDef

    Returns pyamf.ClassAlias
    """
    metadata = []
    if hasattr(class_def, 'DYNAMIC_CLASS_DEF'):
        metadata.append('dynamic')
    elif hasattr(class_def, 'EXTERNALIZABLE_CLASS_DEF'):
        metadata.append('external')
    else:
        metadata.append('static')

    if class_def.amf3 is True:
        metadata.append('amf3')

    class_alias = ClassDefAlias(class_def.class_, class_def.alias,
        attrs=class_def.static_attrs, attr_func=dummy_callable,
        metadata=metadata)
    class_alias.class_def = class_def
    return class_alias

def register_class_def(class_def):
    """Maps a ClassDef to PyAmf.

    This provides the functionality of pyamf.register_class,
    except it maps a ClassDef.

    arguments:
    ===========
     * class_def - amfast.class_def.ClassDef
    """
    if class_def.alias in pyamf.CLASS_CACHE:
        raise PyAmfConversionError("Alias '%s' is already registered." % class_def.alias)

    class_alias = class_def_alias(class_def)
    if pyamf.__version__[1] > 4:
        pyamf.CLASS_CACHE[class_alias.klass] = class_alias
    pyamf.CLASS_CACHE[class_alias.alias] = class_alias

def register_class_mapper(class_mapper):
    """Maps all ClassDefs in a ClassDefMapper to PyAmf.

    arguments:
    ===========
     * class_mapper - amfast.class_def.ClassDefMapper
    """

    for class_def in class_mapper:
        if class_def._built_in is False:
            register_class_def(class_def)

def packet_to_pyamf(amfast_packet):
    """Converts an AmFast Packet to a PyAmf Envelope

    arguments:
    ==========
     * amfast.remoting.Packet

    Returns pyamf.remoting.Evenlope
    """

    version = pyamf.AMF0

    if amfast_packet.client_type == amfast_remoting.Packet.FLASH_8:
        client_type = pyamf.ClientTypes.Flash6
    elif amfast_packet.client_type == amfast_remoting.Packet.FLASH_COM:
        client_type = pyamf.ClientTypes.FlashCom
    elif amfast_packet.client_type == amfast_remoting.Packet.FLASH_9:
        client_type = pyamf.ClientTypes.Flash9
    else:
        client_type = pyamf.ClientTypes.Flash6

    packet = pyamf_remoting.Envelope()
    packet.amfVersion = version
    packet.clientType = client_type

    headers = pyamf_remoting.HeaderCollection()
    for header in amfast_packet.headers:
        headers[header.name] = header.value
        if header.required is True:
            headers.set_required(header.name, value=True)
        else:
            headers.set_required(header.name, value=False)
    packet.headers = headers

    for msg in amfast_packet.messages:
        split_target = msg.target.split('/')
        pyamf_status = '/' + split_target.pop()
        pyamf_target = '/'.join(split_target)
        packet[pyamf_target] = message_to_pyamf(msg, packet, pyamf_status) 

    return packet

def message_to_pyamf(msg, packet, status):
    """Converts an AmFast Message to a PyAmf Response.

    arguments:
    ===========
     * msg - amfast.remoting.Message
     * packet - pyamf.remoting.Envelope
     * status - string

    Returns pyamf.remoting.Response
    """

    message = pyamf_remoting.Response(msg.body)
    message.envelope = packet

    for k, v in pyamf_remoting.STATUS_CODES.iteritems():
        if v == status:
            message.status = k
            break

    return message

#----------- PyAMF Class Extensions ------------#
# Some extra classes to smooth things along with AmFast.

class ClassDefAlias(pyamf.ClassAlias):
    """A pyamf.ClassAlias that uses an amfast.class_def.ClassDef
    on the backend. This class should be instaniated with the
    class_def_alias() function.
    """

    def checkClass(kls, klass):
        # Override parent method, because
        # AmFast does not require that mapped
        # classes' __init__ methods
        # have no required arguments.
        pass

    def getAttrs(self, obj, *args, **kwargs):
        """Returns attribute names in PyAmf format."""
        if hasattr(self.class_def, 'DYNAMIC_CLASS_DEF'):
            dynamic_attrs = self.class_def.getDynamicAttrVals(obj).keys()
        else:
            dynamic_attrs = []

        return (self.class_def.static_attrs, dynamic_attrs)

    def getAttributes(self, obj, *args, **kwargs):
        """Returns attribute values in PyAmf format."""
        if hasattr(self.class_def, 'DYNAMIC_CLASS_DEF'):
            dynamic_attrs = self.class_def.getDynamicAttrVals(obj)
        else:
            dynamic_attrs = {}

        static_attrs = {}
        static_attr_vals = self.class_def.getStaticAttrVals(obj)
        for i in xrange(0, len(self.class_def.static_attrs)):
            static_attrs[self.class_def.static_attrs[i]] = static_attr_vals[i]

        return (static_attrs, dynamic_attrs)

    def applyAttributes(self, obj, attrs, *args, **kwargs):
        """Applies attributes to an instance."""
        self.class_def.applyAttrVals(obj, attrs)

    def createInstance(self, *args, **kwargs):
        """Returns a new instance of the mapped class."""
        return self.class_def.getInstance()

#---- Classes for dealing with ISmallMessage ----#
class DataInputReader(object):
    """A wrapper class for pyamf.amf3.DataInput.
 
    Use this, so we can re-use our existing ISmallMsg reading code.
    """

    def __init__(self, data_input):
        self.data_input = data_input

    def read(self, length):
        return self.data_input.stream.read(length)

    def readElement(self):
        return self.data_input.decoder.readElement()

class PyamfAbstractSmallMsgDef(amfast_messaging.AbstractSmallMsgDef):
    """Decodes ISmallMessages with PyAmf."""

    def readExternal(self, obj, data_input):
        """Overridden to use PyAmf instead of AmFast."""
        flags = self._readFlags(data_input)

        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.BODY_FLAG:
                    obj.body = data_input.readElement()
                else:
                    obj.body = None

                if flag & self.CLIENT_ID_FLAG:
                    obj.clientId = data_input.readElement()
                else:
                    obj.clientId = None

                if flag & self.DESTINATION_FLAG:
                    obj.destination = data_input.readElement()
                else:
                   obj.destination = None

                if flag & self.HEADERS_FLAG:
                    obj.headers = data_input.readElement()
                else:
                    obj.headers = None

                if flag & self.MESSAGE_ID_FLAG:
                    obj.messageId = data_input.readElement()
                else:
                    obj.messageId = None

                if flag & self.TIMESTAMP_FLAG:
                    obj.timestamp = data_input.readElement()
                else:
                    obj.timestamp = None

                if flag & self.TIME_TO_LIVE_FLAG:
                    obj.timeToLive = data_input.readElement()
                else:
                    obj.timeToLive = None

            if i == 1:
                if flag & self.CLIENT_ID_BYTES_FLAG:
                    clientIdBytes = data_input.readElement()
                    obj.clientId = self._readUid(clientIdBytes)
                else:
                    if not hasattr(obj, 'clientId'):
                        obj.clientId = None

                if flag & self.MESSAGE_ID_BYTES_FLAG:
                    messageIdBytes = data_input.readElement()
                    obj.messageId = self._readUid(messageIdBytes)
                else:
                    if not hasattr(obj, 'messageId'):
                        obj.messageId = None

    def getInstance(self):
        """
        Return a regular AmFast AbstractMessage instead of
        the class that has been mapped to this ClassDef.

        Kinda tricky. Muuuuhhahahahah
        """
        obj = amfast_messaging.AbstractMessage.__new__(amfast_messaging.AbstractMessage)

        def readAmf(data_input):
            self.readExternal(obj, DataInputReader(data_input))
        obj.__readamf__ = readAmf
        return obj

class PyamfAsyncSmallMsgDef(amfast_messaging.AsyncSmallMsgDef, PyamfAbstractSmallMsgDef):

    def __init__(self, *args, **kwargs):
        amfast_messaging.AsyncSmallMsgDef.__init__(self, *args, **kwargs)

    def readExternal(self, obj, data_input):
        PyamfAbstractSmallMsgDef.readExternal(self, obj, data_input)

        flags = self._readFlags(data_input)
        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.CORRELATION_ID_FLAG:
                    obj.correlationId = data_input.readElement()
                else:
                    obj.correlationId = None

                if flag & self.CORRELATION_ID_BYTES_FLAG:
                    correlationIdBytes = data_input.readElement()
                    obj.correlationId = self._readUid(correlationIdBytes)
                else:
                    if not hasattr(obj, 'correlationId'):
                        obj.correlationId = None

    def getInstance(self):
        obj = amfast_messaging.AsyncMessage.__new__(amfast_messaging.AsyncMessage)

        def readAmf(data_input):
            self.readExternal(obj, DataInputReader(data_input))
        obj.__readamf__ = readAmf
        return obj

class PyamfCommandSmallMsgDef(amfast_messaging.CommandSmallMsgDef, PyamfAsyncSmallMsgDef):

    def __init__(self, *args, **kwargs):
        amfast_messaging.CommandSmallMsgDef.__init__(self, *args, **kwargs)

    def readExternal(self, obj, data_input):
        PyamfAsyncSmallMsgDef.readExternal(self, obj, data_input)

        flags = self._readFlags(data_input)
        for i, flag in enumerate(flags):
            if i == 0:
                if flag & self.OPERATION_FLAG:
                    obj.operation = data_input.readElement()
                else:
                    obj.operation = None

    def getInstance(self):
        obj = amfast_messaging.CommandMessage.__new__(amfast_messaging.CommandMessage)

        def readAmf(data_input):
            self.readExternal(obj, DataInputReader(data_input))
        obj.__readamf__ = readAmf
        return obj

# ---- Dummy classes to trick PyAmf into doing what we want. ---#
class SmallAbstractMsg(amfast_messaging.AbstractMessage):
    def __readamf__(self, data_input):
        raise pyamf.EncodeError("__readamf__ is not implemented for this class: %s." % self)

    def __writeamf__(self, data_output):
        raise pyamf.EncodeError("__writeamf__ is not implemented for this class: %s." % self)

class SmallAsyncMsg(amfast_messaging.AsyncMessage):
    def __readamf__(self, data_input):
        raise pyamf.EncodeError("__readamf__ is not implemented for this class: %s." % self)

    def __writeamf__(self, data_output):
        raise pyamf.EncodeError("__writeamf__ is not implemented for this class: %s." % self)

class SmallCommandMsg(amfast_messaging.CommandMessage):
    def __readamf__(self, data_input):
        raise pyamf.EncodeError("__readamf__ is not implemented for this class: %s." % self)

    def __writeamf__(self, data_output):
        raise pyamf.EncodeError("__writeamf__ is not implemented for this class: %s." % self)

#----- Map Flex message classes with PyAmf -----#

# Clear existing message class mappings,
# then re-map with AmFast ClassDefs.

#---- AbstractMessage ---#
try:
    pyamf.unregister_class('flex.messaging.messages.AbstractMessage')
except pyamf.UnknownClassAlias:
    pass
register_class_def(class_def.ClassDef(amfast_messaging.AbstractMessage))

#---- AsyncMessage ----#
try:
    pyamf.unregister_class('flex.messaging.messages.AsyncMessage')
except pyamf.UnknownClassAlias:
    pass

try:
    pyamf.unregister_class('DSA')
except pyamf.UnknownClassAlias:
    pass

register_class_def(class_def.ClassDef(amfast_messaging.AsyncMessage))
register_class_def(PyamfAsyncSmallMsgDef(SmallAsyncMsg, 'DSA',
    ('body', 'clientId', 'destination', 'headers', 'messageId',
        'timeToLive', 'timestamp', 'correlationId')))

#---- AcknowledgeMessage --#
try:
    pyamf.unregister_class('flex.messaging.messages.AcknowledgeMessage')
except pyamf.UnknownClassAlias:
    pass

try:
    pyamf.unregister_class('DSK')
except pyamf.UnknownClassAlias:
    pass

register_class_def(class_def.ClassDef(amfast_messaging.AcknowledgeMessage))

#---- CommandMessage ----#
try:
    pyamf.unregister_class('flex.messaging.messages.CommandMessage')
except pyamf.UnknownClassAlias:
    pass

try:
    pyamf.unregister_class('DSC')
except pyamf.UnknownClassAlias:
    pass

register_class_def(class_def.ClassDef(amfast_messaging.CommandMessage))
register_class_def(PyamfCommandSmallMsgDef(SmallCommandMsg, 'DSC',
    ('body', 'clientId', 'destination', 'headers', 'messageId',
        'timeToLive', 'timestamp', 'correlationId', 'operation')))

#---- ErrorMessage ----#
try:
    pyamf.unregister_class('flex.messaging.messages.ErrorMessage')
except pyamf.UnknownClassAlias:
    pass

register_class_def(class_def.ClassDef(amfast_messaging.ErrorMessage))


#---- RemotingMessage ----#
try:
    pyamf.unregister_class('flex.messaging.messages.RemotingMessage')
except pyamf.UnknownClassAlias:
    pass

register_class_def(class_def.ClassDef(amfast_messaging.RemotingMessage))
