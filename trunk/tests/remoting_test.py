import unittest
import logging
import sys

import amfast
from amfast import remoting, logger
from amfast.encoder import Encoder
from amfast.decoder import Decoder
from amfast.remoting import ServiceMapper, flex_messages as messaging
from amfast.remoting.channel import ChannelSet, Channel

#handler = logging.StreamHandler(sys.stdout)
#handler.setLevel(logging.DEBUG)
#logger.addHandler(handler)
#amfast.log_debug = True

class RemotingTestCase(unittest.TestCase):

    def setUp(self):
        self.service_mapper = ServiceMapper()

        # Map example function to target
        self.target_name = 'Credentials'
        target = remoting.CallableTarget(self.login, self.target_name)

        # Map header targets
        self.service_mapper.packet_header_service.mapTarget(target)

        # Map message targets
        self.service_name = 'login'
        service = remoting.Service(self.service_name)
        service.mapTarget(target)
        self.service_mapper.mapService(service)

        # Valid values for the target
        self.arg = {'userid': 'userid', 'password': 'password'}

        # Setup Encoder and Decoder
        self.channel_set = ChannelSet(service_mapper=self.service_mapper)
        self.channel = Channel('amf_rpc')
        self.channel_set.mapChannel(self.channel)

    def tearDown(self):
        pass

    def login(self, credentials):
        self.assertEquals(self.arg['userid'], credentials['userid'])
        self.assertEquals(self.arg['password'], credentials['password'])
        return True

    def testDecodeRpcPacket(self):
        encoded = '\x00\x00' # AMF0 version marker
        encoded += '\x00\x02' # Header count (2)
        encoded += '\x00\x04spam\x00\x00\x00\x00\x07\x02\x00\x04eggs' # Optional Header 
        encoded += '\x00\x04eggs\x01\x00\x00\x00\x07\x02\x00\x04spam' # Required Header
        encoded += '\x00\x02' # Body count (2)
        #1st message body
        encoded += '\x00\x04spam' # Body target
        encoded += '\x00\x04eggs' # Body response
        encoded += '\x00\x00\x00\x07' # Body byte length
        encoded += '\x0A\x00\x00\x00\x01' # Body start - 1 element array header
        encoded += '\x01\x01' # Body[0] 1 value
        #2nd message body
        encoded += '\x00\x04eggs' # Body 2 target
        encoded += '\x00\x04spam' # Body 2 response
        encoded += '\x00\x00\x00\x07' # Body 2 byte length
        encoded += '\x0A\x00\x00\x00\x01' # Body start - 1 element array header
        encoded += '\x01\x00' # Body 2 value

        packet = self.channel.endpoint.decodePacket(encoded)

        # version
        self.assertEquals(packet.FLASH_8, packet.client_type)

        # headers
        self.assertEquals('eggs', packet.headers[0].value)
        self.assertEquals(False, packet.headers[0].required)
        self.assertEquals('spam', packet.headers[0].name)

        self.assertEquals('spam', packet.headers[1].value)
        self.assertEquals(True, packet.headers[1].required)
        self.assertEquals('eggs', packet.headers[1].name)

        # messages
        self.assertEquals('spam', packet.messages[0].target)
        self.assertEquals('eggs', packet.messages[0].response)
        self.assertEquals(True, packet.messages[0].body[0])

        self.assertEquals('eggs', packet.messages[1].target)
        self.assertEquals('spam', packet.messages[1].response)
        self.assertEquals(False, packet.messages[1].body[0])

    def testDecodeReponsePacket(self):
        encoded = '\x00\x00' # AMF0 version marker
        encoded += '\x00\x01' # Header count
        encoded += '\x00\x04spam\x00\x00\x00\x00\x07\x02\x00\x04eggs' # Optional Header 
        encoded += '\x00\x01' # Body count
        #1st message body
        encoded += '\x00\x04spam' # Body target
        encoded += '\x00\x00' # Body response
        encoded += '\x00\x00\x00\x02' # Body byte length
        encoded += '\x01\x01' # Body value

        packet = self.channel.endpoint.decodePacket(encoded)

        # version
        self.assertEquals(packet.FLASH_8, packet.client_type)

        # headers
        self.assertEquals('eggs', packet.headers[0].value)
        self.assertEquals(False, packet.headers[0].required)
        self.assertEquals('spam', packet.headers[0].name)

        # messages
        self.assertEquals('spam', packet.messages[0].target)
        self.assertEquals('', packet.messages[0].response)
        self.assertEquals(True, packet.messages[0].body)

    def testRoundTripPacket(self):
        encoded = '\x00\x00' # AMF0 version marker
        encoded += '\x00\x02' # Header count (2)
        encoded += '\x00\x04spam\x00\x00\x00\x00\x07\x02\x00\x04eggs' # Optional Header 
        encoded += '\x00\x04eggs\x01\x00\x00\x00\x07\x02\x00\x04spam' # Required Header
        encoded += '\x00\x02' # Body count (2)
        #1st message body
        encoded += '\x00\x04spam' # Body target
        encoded += '\x00\x04eggs' # Body response
        encoded += '\x00\x00\x00\x07' # Body byte length
        encoded += '\x0A\x00\x00\x00\x01' # Body start - 1 element array header
        encoded += '\x01\x01' # Body[0] 1 value
        #2nd message body
        encoded += '\x00\x04eggs' # Body 2 target
        encoded += '\x00\x04spam' # Body 2 response
        encoded += '\x00\x00\x00\x07' # Body 2 byte length
        encoded += '\x0A\x00\x00\x00\x01' # Body start - 1 element array header
        encoded += '\x01\x00' # Body 2 value

        packet = self.channel.endpoint.decodePacket(encoded)
        encoded_packet = self.channel.endpoint.encodePacket(packet)
        self.assertEquals(encoded, encoded_packet)

    def testHeaderTarget(self):
        header = remoting.Header(self.target_name, False, self.arg)
        packet = remoting.Packet(headers=[header])
        packet.channel = self.channel
        packet.invoke()

    def testOldStyleTarget(self):
        qualified_name = self.service_name + '.' + self.target_name
        message = remoting.Message(target=qualified_name, response='/1',
            body=(self.arg,))
        packet = remoting.Packet(messages=[message])
        packet.channel = self.channel
        response = packet.invoke()
        
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)
        self.assertEquals(True, response.messages[0].body)

    def testOldStyleTargetFault(self):
        message = remoting.Message(target='bad_target', response='/1',
            body=(self.arg,))
        packet = remoting.Packet(messages=[message])
        packet.channel = self.channel
        response = packet.invoke()

        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onStatus'))
        self.assertEquals('', response.messages[0].response)
        self.assertEquals(remoting.AsError, response.messages[0].body.__class__)

    def testRoTarget(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.RemotingMessage()
        inner_msg.destination = self.service_name
        inner_msg.operation = self.target_name
        inner_msg.headers = {self.target_name: self.arg, 'DSEndpoint': 'amf'}
        inner_msg.body = (self.arg,)
        inner_msg.messageId = '123'
        outter_msg.body = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        packet.channel = self.channel
        response = packet.invoke()

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(True, response.messages[0].body.body)
        self.assertEquals('123', response.messages[0].body.correlationId)

    def testRoTargetFault(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.RemotingMessage()
        inner_msg.destination = 'fault'
        inner_msg.operation = self.target_name
        inner_msg.headers = {self.target_name: self.arg, 'DSEndpoint': 'amf'}
        inner_msg.body = (self.arg,)
        inner_msg.messageId = '123'
        outter_msg.body = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        packet.channel = self.channel
        response = packet.invoke()

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onStatus'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(messaging.ErrorMessage, response.messages[0].body.__class__)
        self.assertEquals('123', response.messages[0].body.correlationId)

    def testRoPing(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.CommandMessage()
        inner_msg.destination = self.service_name
        inner_msg.operation = messaging.CommandMessage.CLIENT_PING_OPERATION
        inner_msg.headers = {'DSEndpoint': 'amf'}
        inner_msg.body = ()
        inner_msg.messageId = '123'
        outter_msg.body = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        packet.channel = self.channel
        response = packet.invoke()

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(messaging.AcknowledgeMessage, response.messages[0].body.__class__)
        self.assertEquals('123', response.messages[0].body.correlationId)

    def testProcessPacket(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.CommandMessage()
        inner_msg.destination = self.service_name
        inner_msg.operation = messaging.CommandMessage.CLIENT_PING_OPERATION
        inner_msg.headers = {'DSEndpoint': 'amf'}
        inner_msg.body = (None, )
        inner_msg.messageId = '123'
        outter_msg.body = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        encoded_packet = self.channel.encode(packet)
        decoded_packet = self.channel.decode(encoded_packet)
        response = self.channel.invoke(decoded_packet)
        encoded_response = self.channel.encode(response)
        response = self.channel.endpoint.decodePacket(encoded_response)

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(messaging.AcknowledgeMessage, response.messages[0].body.__class__)
        self.assertEquals('123', response.messages[0].body.correlationId)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RemotingTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

