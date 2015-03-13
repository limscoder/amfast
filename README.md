##AmFast

A Flash remoting framework for Python that uses AMF to communicate between Python and Flash, Flex, and any other system that supports AMF.

##Server Features

 * Support for NetConnection and RemoteObject RPC.
 * Support for Producer/Consumer 'push' messaging with HTTP polling, HTTP long-polling, and real-time HTTP streaming channels.
 * Support for authentication with NetConnection and RemoteObject.
 * Built in Channels for CherryPy, Twisted Web, Google App Engine, Django, Tornado and plain WSGI.
 * Support for configurable Endpoints. Use AmFast's built-in AMF encoder/decoder C-extension, or use an external AMF encoder/decoder, such as PyAmf for a pure-Python implementation.

##AMF Encoder/Decoder Features

 * AMF0/AMF3 encoder/decoder written in C as a Python extension for speed.
 * Map custom classes with ClassDef objects for complete control over serialization/de-serialization.
 * Full support for IExternalizable objects.
 * Data persistence with SqlAlchemy including remotely-loadable lazy-loaded attributes.
 * Actionscript code generation from ClassDef objects.

##Installation

Most current version is: 0.5.3
Download the package distribution from PyPi
Extract package and execute the following command from within the root distribution directory:

    # To install entire package:
    python setup.py install
    
    # Install without compiling encode/decode extensions.
    #
    # If you don't compile the encode/decode extensions,
    # you can use PyAmf for encoding/decoding.
    python setup.py --without-extensions install

Copyright (c) 2009 Dave Thompson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
