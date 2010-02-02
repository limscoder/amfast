import amfast
from gae_connection_manager import GaeConnectionManager
from gae_subscription_manager import GaeSubscriptionManager
from pyamf_endpoint import PyAmfEndpoint
from wsgi_channel import WsgiChannelSet, WsgiChannel

class GaeChannelSet(WsgiChannelSet):

    # Access this URL to clean-up stale connection data.
    CLEAN_URL = '_clean'

    def __init__(self, service_mapper=None, connection_manager=None,
        subscription_manager=None):

        if connection_manager is None:
            connection_manager = GaeConnectionManager()

        if subscription_manager is None:
            subscription_manager = GaeSubscriptionManager()

        WsgiChannelSet.__init__(self, service_mapper=service_mapper,
            connection_manager=connection_manager,
            subscription_manager=subscription_manager,
            clean_freq=100000)

    def __call__(self, environ, start_response):
        channel_name = environ['PATH_INFO'][1:]
        if channel_name == self.CLEAN_URL:
            self.clean()
            return

        channel = self.getChannel(channel_name)
        return channel(environ, start_response)

    def notifyConnections(self):
        pass

    def scheduleClean(self):
        amfast.logger.warn("Cron.yaml must be configured to access the URL: self.CLEAN_URL to clean-up any stale connections.")

class GaeChannel(WsgiChannel):
    def __init__(self, *args, **kwargs):
        # Overriden to set default endpoint as PyAmfEndpoint.
        if len(args) < 3 and ('endpoint' not in kwargs):
            kwargs['endpoint'] = PyAmfEndpoint()

        WsgiChannel.__init__(self, *args, **kwargs)
