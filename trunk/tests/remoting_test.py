import unittest
import logging
import sys

from amfast import remoting, logger
from amfast.remoting import flex_messages as messaging

#handler = logging.StreamHandler(sys.stdout)
#handler.setLevel(logging.DEBUG)
#logger.addHandler(handler)

class RemotingTestCase(unittest.TestCase):

    def setUp(self):
        self.gateway = remoting.Gateway()

        # Map example function to target
        self.target_name = 'Credentials'
        target = remoting.CallableTarget(self.login, self.target_name)

        # Map header targets
        self.gateway.service_mapper.packet_header_service.setTarget(target)
        self.gateway.service_mapper.message_header_service.setTarget(target)

        # Map message targets
        self.service_name = 'login'
        service = remoting.Service(self.service_name)
        service.setTarget(target)
        self.gateway.service_mapper.mapService(service)

        # Valid values for the target
        self.arg = {'userid': 'userid', 'password': 'password'}

    def tearDown(self):
        pass

    def login(self, credentials):
        self.assertEquals(self.arg['userid'], credentials['userid'])
        self.assertEquals(self.arg['password'], credentials['password'])
        return True

    def testDecodePacket(self):
        encoded = '\x00\x00' # AMF0 version marker
        encoded += '\x00\x02' # Header count
        encoded += '\x00\x04spam\x00\x00\x00\x00\x07\x02\x00\x04eggs' # Optional Header
        encoded += '\x00\x04eggs\x01\x00\x00\x00\x07\x02\x00\x04spam' # Required Header , 32 bytes
        encoded += '\x00\x02' # Body count
        encoded += '\x00\x04spam' # Body 1 target
        encoded += '\x00\x04eggs' # Body 1 response
        encoded += '\x00\x00\x00\x0E' # Body 1 byte length
        encoded += '\x01\x01' # Body 1 value
        encoded += '\x00\x04eggs' # Body 2 target
        encoded += '\x00\x04spam' # Body 2 response
        encoded += '\x00\x00\x00\x0E' # Body 2 byte length
        encoded += '\x01\x00' # Body 2 value

        packet = self.gateway.decode_packet(encoded)

        # version
        self.assertEquals(packet.FLASH_8, packet.version)

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
        self.assertEquals(True, packet.messages[0].value)

        self.assertEquals('eggs', packet.messages[1].target)
        self.assertEquals('spam', packet.messages[1].response)
        self.assertEquals(False, packet.messages[1].value)

    def testRoundTripPacket(self):
        encoded = '\x00\x00' # AMF0 version marker
        encoded += '\x00\x02' # Header count
        encoded += '\x00\x04spam\x00\x00\x00\x00\x07\x02\x00\x04eggs' # Optional Header
        encoded += '\x00\x04eggs\x01\x00\x00\x00\x07\x02\x00\x04spam' # Required Header , 32 bytes
        encoded += '\x00\x02' # Body count
        encoded += '\x00\x04spam' # Body 1 target
        encoded += '\x00\x04eggs' # Body 1 response
        encoded += '\x00\x00\x00\x02' # Body 1 byte length
        encoded += '\x01\x01' # Body 1 value
        encoded += '\x00\x04eggs' # Body 2 target
        encoded += '\x00\x04spam' # Body 2 response
        encoded += '\x00\x00\x00\x02' # Body 2 byte length
        encoded += '\x01\x00' # Body 2 value

        packet = self.gateway.decode_packet(encoded)
        encoded_packet = self.gateway.encode_packet(packet)
        self.assertEquals(encoded, encoded_packet)

    def testHeaderTarget(self):
        header = remoting.Header(self.target_name, False, self.arg)
        packet = remoting.Packet(headers=[header])
        packet.invoke(self.gateway.service_mapper)

    def testOldStyleTarget(self):
        qualified_name = self.service_name + '.' + self.target_name
        message = remoting.Message(target=qualified_name, response='/1',
            value=(self.arg,))
        packet = remoting.Packet(messages=[message])
        response = packet.invoke(self.gateway.service_mapper)
        
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)
        self.assertEquals(True, response.messages[0].value)

    def testOldStyleTargetFault(self):
        message = remoting.Message(target='bad_target', response='/1',
            value=(self.arg,))
        packet = remoting.Packet(messages=[message])
        response = packet.invoke(self.gateway.service_mapper)

        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onStatus'))
        self.assertEquals('', response.messages[0].response)
        self.assertEquals(remoting.AsError, response.messages[0].value.__class__)

    def testRoTarget(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.RemotingMessage()
        inner_msg.destination = self.service_name
        inner_msg.operation = self.target_name
        inner_msg.headers = {self.target_name: self.arg}
        inner_msg.body = (self.arg,)
        inner_msg.messageId = '123'
        outter_msg.value = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        response = packet.invoke(self.gateway.service_mapper)

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(True, response.messages[0].value.body)
        self.assertEquals('123', response.messages[0].value.correlationId)

    def testRoTargetFault(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.RemotingMessage()
        inner_msg.destination = 'fault'
        inner_msg.operation = self.target_name
        inner_msg.headers = {self.target_name: self.arg}
        inner_msg.body = (self.arg,)
        inner_msg.messageId = '123'
        outter_msg.value = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        response = packet.invoke(self.gateway.service_mapper)

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onStatus'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(messaging.ErrorMessage, response.messages[0].value.__class__)
        self.assertEquals('123', response.messages[0].value.correlationId)

    def testRoPing(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.CommandMessage()
        inner_msg.destination = self.service_name
        inner_msg.operation = messaging.CommandMessage.CLIENT_PING_OPERATION
        inner_msg.headers = {}
        inner_msg.body = ()
        inner_msg.messageId = '123'
        outter_msg.value = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        response = packet.invoke(self.gateway.service_mapper)

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(messaging.AcknowledgeMessage, response.messages[0].value.__class__)
        self.assertEquals('123', response.messages[0].value.correlationId)
        self.assertEquals(True, response.messages[0].value.body)

    def testProcessPacket(self):
        outter_msg = remoting.Message(target='null', response='/1')
        inner_msg = messaging.CommandMessage()
        inner_msg.destination = self.service_name
        inner_msg.operation = messaging.CommandMessage.CLIENT_PING_OPERATION
        inner_msg.headers = {}
        inner_msg.body = (None, )
        inner_msg.messageId = '123'
        outter_msg.value = (inner_msg, )

        packet = remoting.Packet(messages=[outter_msg])
        encoded_packet = self.gateway.encode_packet(packet)
        encoded_response = self.gateway.process_packet(encoded_packet)
        response = self.gateway.decode_packet(encoded_response)

        # Check outer msg
        self.assertEquals(1, len(response.messages))
        self.assertEquals(True, response.messages[0].target.endswith('onResult'))
        self.assertEquals('', response.messages[0].response)

        # Check inner msg
        self.assertEquals(messaging.AcknowledgeMessage, response.messages[0].value.__class__)
        self.assertEquals('123', response.messages[0].value.correlationId)
        self.assertEquals(True, response.messages[0].value.body)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RemotingTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

