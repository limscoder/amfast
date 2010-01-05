from google.appengine.ext.webapp.util import run_wsgi_app

import amfast
from amfast.remoting.gae_channel import GaeChannelSet, GaeChannel

# Setup AmFast here.
# This code gets run once per webserver.
amfast.log_debug = False # Set to True to log AmFast debug messages
channel_set = GaeChannelSet()
channel_set.mapChannel(GaeChannel('amf'))

def main():
    """
    GAE handlers with a 'main' function are cached.
    Every request will cause this function to be called.

    'run_wsgi_app' converts CGI requests to WSGI requests.
    """

    run_wsgi_app(channel_set)

if __name__ == "__main__":
    main()
