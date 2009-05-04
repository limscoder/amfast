"""Utility functions."""
import sys
import logging

import amfast
from amfast.encoder import Encoder
from amfast.decoder import Decoder
from amfast.remoting import Service, CallableTarget

import controller

def setup_channel_set(channel_set):
    """Configures an amfast.remoting.channel.ChannelSet object."""

    # Send log messages to STDOUT
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    amfast.logger.addHandler(handler)

    # Map service targets to controller methods
    cont_obj = controller.Controller()
    service = Service('ExampleService')

    # Set secure=True to raise an exception
    # when an un-authenticated user attempts
    # to access the target. 
    service.mapTarget(CallableTarget(cont_obj.echo, 'echo', secure=True))
    channel_set.service_mapper.mapService(service)

    # Set the ChannelSet's 'checkCredentials' attribute
    # to enable authentication.
    #
    # In this example, we're using a method from the
    # controller to check credentials.
    channel_set.checkCredentials = cont_obj.checkCredentials
