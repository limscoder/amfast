"""Utility functions."""
import sys
import logging

import amfast
from amfast.class_def.sa_class_def import SaClassDef
from amfast.remoting import Service, CallableTarget

import persistent
import controller
import models

def setup_gateway(gateway):
    """configures a amfast.remoting.Gateway object."""

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
    gateway.class_def_mapper.mapClass(SaClassDef(models.User, 'models.User'))
    gateway.class_def_mapper.mapClass(SaClassDef(models.Email, 'models.Email'))
    gateway.class_def_mapper.mapClass(SaClassDef(models.PhoneNumber, 'models.PhoneNumber'))

    # Map controller methods to service targets
    sa_obj = controller.SAObject()
    sa_obj.gateway = gateway
    service = Service('ExampleService')
    service.setTarget(CallableTarget(sa_obj.load, 'load'))
    service.setTarget(CallableTarget(sa_obj.loadAttr, 'loadAttr'))
    service.setTarget(CallableTarget(sa_obj.loadAll, 'loadAll'))
    service.setTarget(CallableTarget(sa_obj.saveList, 'saveList'))
    service.setTarget(CallableTarget(sa_obj.save, 'save'))
    service.setTarget(CallableTarget(sa_obj.remove, 'remove'))
    service.setTarget(CallableTarget(sa_obj.removeList, 'removeList'))
    service.setTarget(CallableTarget(sa_obj.insertDefaultData, 'insertDefaultData'))
    service.setTarget(CallableTarget(sa_obj.raiseException, 'raiseException'))
    gateway.service_mapper.mapService(service)
