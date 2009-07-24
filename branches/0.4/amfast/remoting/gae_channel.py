from gae_connection_manager import GaeConnectionManager
from gae_subscription_manager import GaeSubscriptionManager
from pyamf_endpoint import PyAmfEndpoint
from wsgi_channel import WsgiChannelSet, WsgiChannel

class GaeChannelSet(WsgiChannelSet):
    def __init__(self, service_mapper=None, connection_manager=None,
        subscription_manager=None, clean_freq=300):

        if connection_manager is None:
            connection_manager = GaeConnectionManager()

        if subscription_manager is None:
            subscription_manager = GaeSubscriptionManager()

        WsgiChannelSet.__init__(self, service_mapper=service_mapper,
            connection_manager=connection_manager,
            subscription_manager=subscription_manager,
            clean_freq=clean_freq)

    def scheduleClean(self):
        # TODO: clean database.
        pass

class GaeChannel(WsgiChannel):
    def __init__(self, *args, **kwargs):

        # We can't use AmFast's encoder/decoder
        # since extensions won't work properly.
        key = 'endpoint'
        if key not in kwargs:
            kwargs[key] = PyAmfEndpoint()

        WsgiChannel.__init__(self, *args, **kwargs) 
