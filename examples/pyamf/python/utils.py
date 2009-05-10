"""Utility functions."""
import sys
import logging

import amfast
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
    service.mapTarget(CallableTarget(cont_obj.echo, 'echo'))
    service.mapTarget(CallableTarget(cont_obj.raiseException, 'raiseException'))
    channel_set.service_mapper.mapService(service)
