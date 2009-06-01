class Subscription(object):
    """An MessageAgent's subscription to a topic. 
 
    attributes 
    =========== 
     * connection_id - Connection, the connection_id the Subscription belongs to. 
     * client_id - string, the MessageAgent's clientId. 
     * topic - string, the name of the topic subscribed to. The 
         topic string also contains the sub-topic. 
    """

    def __init__(self, connection_id, client_id, topic):
        self.connection_id = connection_id # Unique for each Flex client
        self.client_id = client_id # Unique for each MessageAgent 
        self.topic = topic
