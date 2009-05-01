"""Utility functions."""
import sys
import logging

import amfast
from amfast.encoder import Encoder
from amfast.decoder import Decoder
from amfast.class_def import ClassDefMapper, DynamicClassDef, ExternClassDef
from amfast.remoting import Service, CallableTarget

class RemoteClass(object):
    pass

class ExternClass(object):
    pass

def echo(val):
    return val

def setup_channel_set(channel_set):
    """Configures an amfast.remoting.channel.ChannelSet object."""

    # Send log messages to STDOUT
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    amfast.logger.addHandler(handler)

    # These classes are for interacting with the Red5 echo test client.
    class_mapper = ClassDefMapper()
    class_mapper.mapClass(DynamicClassDef(RemoteClass,
        'org.red5.server.webapp.echo.RemoteClass', amf3=False))
    class_mapper.mapClass(ExternClassDef(ExternClass,
        'org.red5.server.webapp.echo.ExternalizableClass'))

    # Set Channel options
    # We're going to use the same
    # Encoder and Decoder for all channels
    encoder = Encoder(use_collections=True, use_proxies=True,
        class_def_mapper=class_mapper, use_legacy_xml=True)
    decoder = Decoder(class_def_mapper=class_mapper)
    for channel in channel_set:
        channel.endpoint.encoder = encoder
        channel.endpoint.decoder = decoder

    # Map service targets to controller methods
    channel_set.service_mapper.default_service.mapTarget(CallableTarget(echo, 'echo'))
    service = Service('Red5Echo')
    service.mapTarget(CallableTarget(echo, 'echo'))
    channel_set.service_mapper.mapService(service)
