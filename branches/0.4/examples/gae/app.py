from google.appengine.ext.webapp.util import run_wsgi_app

import amfast
from amfast.remoting.gae_channel import GaeChannelSet, GaeChannel

def main():
    amfast.log_debug = False # Set to True to log debug messages
    channel_set = GaeChannelSet()
    channel_set.mapChannel(GaeChannel('amf'))
    run_wsgi_app(channel_set)

if __name__ == "main":
    main()
