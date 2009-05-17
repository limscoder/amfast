"""Utility functions."""
import sys
import logging
from datetime import datetime
from threading import Timer

import amfast
from amfast.encoder import Encoder
from amfast.decoder import Decoder
from amfast.class_def import ClassDefMapper, DynamicClassDef, ExternClassDef
from amfast.class_def.sa_class_def import SaClassDef
from amfast.class_def.code_generator import CodeGenerator
from amfast.remoting import Service, CallableTarget

import persistent
import controller
import models

def setup_channel_set(channel_set):
    """Configures an amfast.remoting.channel.ChannelSet object."""

    # Setup database
    schema = persistent.Schema()
    schema.createSchema()
    schema.createMappers()

    # Send log messages to STDOUT
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    amfast.logger.addHandler(handler)

    # Map class aliases
    # These same aliases must be
    # registered in the client
    # with the registClassAlias function,
    # or the RemoteClass metadata tag.
    class_mapper = ClassDefMapper()
    class_mapper.mapClass(SaClassDef(models.User, 'models.User'))
    class_mapper.mapClass(SaClassDef(models.Email, 'models.Email'))
    class_mapper.mapClass(SaClassDef(models.PhoneNumber, 'models.PhoneNumber'))

    # Expose class_mapper to our controller
    sa_obj = controller.SAObject()
    sa_obj.class_def_mapper = class_mapper

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
    service = Service('ExampleService')
    service.mapTarget(CallableTarget(sa_obj.load, 'load'))
    service.mapTarget(CallableTarget(sa_obj.loadAttr, 'loadAttr'))
    service.mapTarget(CallableTarget(sa_obj.loadAll, 'loadAll'))
    service.mapTarget(CallableTarget(sa_obj.saveList, 'saveList'))
    service.mapTarget(CallableTarget(sa_obj.save, 'save'))
    service.mapTarget(CallableTarget(sa_obj.remove, 'remove'))
    service.mapTarget(CallableTarget(sa_obj.removeList, 'removeList'))
    service.mapTarget(CallableTarget(sa_obj.insertDefaultData, 'insertDefaultData'))
    channel_set.service_mapper.mapService(service)

    # Generate source code for mapped models
    #coder = CodeGenerator()
    #coder.generateFilesFromMapper(gateway.class_def_mapper, use_accessors=False,
    #    packaged=True, constructor=False, bindable=True, extends='SAObject')
