"""Utility functions."""
import sys
import logging

import amfast
from amfast.class_def import DynamicClassDef, ExternizeableClassDef
from amfast.class_def.sa_class_def import SaClassDef
from amfast.class_def.code_generator import CodeGenerator
from amfast.remoting import Service, CallableTarget

import persistent
import controller
import models

def setup_gateway(gateway):
    """Configures an amfast.remoting.Gateway object."""

    # Setup database
    schema = persistent.Schema()
    schema.createSchema()
    schema.createMappers()

    # Send log messages to STDOUT
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    amfast.logger.addHandler(handler)

    # Set Gateway options
    gateway.use_array_collections = True
    gateway.use_object_proxies = True

    # Map class aliases
    # These same aliases must be
    # registered in the client
    # with the registClassAlias function,
    # or the RemoteClass metadata tag.
    gateway.class_def_mapper.mapClass(SaClassDef(models.User, 'models.User'))
    gateway.class_def_mapper.mapClass(SaClassDef(models.Email, 'models.Email'))
    gateway.class_def_mapper.mapClass(SaClassDef(models.PhoneNumber, 'models.PhoneNumber'))
    gateway.class_def_mapper.mapClass(DynamicClassDef(models.RemoteClass,
        'org.red5.server.webapp.echo.RemoteClass', amf3=False))
    gateway.class_def_mapper.mapClass(ExternizeableClassDef(models.ExternClass,
        'org.red5.server.webapp.echo.ExternalizableClass'))

    # Map controller methods to service targets
    sa_obj = controller.SAObject()
    sa_obj.gateway = gateway
    sa_obj.gateway.service_mapper.default_service.setTarget(CallableTarget(sa_obj.echo, 'echo'))
    service = Service('Red5Echo')
    service.setTarget(CallableTarget(sa_obj.echo, 'echo'))
    gateway.service_mapper.mapService(service)
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

    # Generate source code for mapped models
    #coder = CodeGenerator()
    #coder.generateFilesFromMapper(gateway.class_def_mapper, use_accessors=False,
    #    packaged=True, constructor=False, bindable=True, extends='SAObject')

