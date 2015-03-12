# Description #
  * AmFast is a Flash remoting framework for Python.
  * AmFast can use AMF to communicate between Python and Flash, Flex, and any other system that supports AMF.

# Server Features #
  * Support for NetConnection and RemoteObject [RPC](MessagingServer#Mapping_RPC_Destinations.md).
  * Support for [Producer/Consumer](MessagingServer#Producer/Consumer_Messaging.md) 'push' messaging with HTTP polling, HTTP long-polling, and real-time HTTP streaming channels.
  * Support for [authentication](MessagingServer#Authentication.md) with NetConnection and RemoteObject.
  * Built in Channels for [CherryPy](http://cherrypy.org), [Twisted Web](http://twistedmatrix.com/trac/), [Google App Engine](http://code.google.com/appengine/), [Django](http://www.djangoproject.com/,), [Tornado](http://www.tornadoweb.org/) and plain WSGI.
  * Support for [configurable Endpoints](MessagingServer#Configurable_Endpoints.md). Use AmFast's built-in AMF encoder/decoder C-extension, or use an external AMF encoder/decoder, such as [PyAmf](http://pyamf.org/) for a pure-Python implementation.

# AMF Encoder/Decoder Features #
  * AMF0/AMF3 encoder/decoder written in C as a Python extension for speed.
  * [Faster](Faq#How_much_faster_is_AmFast_compared_with_PyAmf_?.md) than [PyAmf](http://pyamf.org/) encoder/decoder.
  * [Map custom classes](EncodeAndDecode#Custom_Type_Maps.md) with ClassDef objects for complete control over serialization/de-serialization.
  * Full support for IExternalizable objects.
  * Data persistence with [SqlAlchemy](http://www.sqlalchemy.org/) including remotely-loadable lazy-loaded attributes.
  * Actionscript code generation from ClassDef objects.

# Installation #
  * Most current version is: 0.5.3
  * [Download the package distribution from PyPi](http://pypi.python.org/pypi?:action=display&name=AmFast&version=0.5.3-r541)
  * Extract package and execute the following command from within the root distribution directory:
```
# To install entire package:
python setup.py install

# Install without compiling encode/decode extensions.
#
# If you don't compile the encode/decode extensions,
# you can use PyAmf for encoding/decoding.
python setup.py --without-extensions install
```
  * [Compiling the encoder/decoder extensions for Windows](Faq#How_do_I_get_the_encoder/decoder_extensions_to_compile_in_Window.md)

# Documentation #
  * [Documentation](Documentation.md)
  * [Examples](ExampleImplementations.md)

# Discuss #
  * [AmFast Group](http://groups.google.com/group/amfast)

# About #
  * [About the AmFast project](AmFastProject.md)