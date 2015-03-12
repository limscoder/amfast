# EchoTest Example. #

This example uses [Red5 project](http://code.google.com/p/red5/)'s echo test application.

The example is located in SVN within the [examples/echo](http://code.google.com/p/amfast/source/browse/trunk/examples/echo) directory

The example has scripts for serving the application via [CherryPy](http://www.cherrypy.org/), [Twisted Web](http://twistedmatrix.com/trac/), or WSGI.

Start the server and point your browser to http://localhost:8000

To run the tests, enter http://localhost:8000/amf in the 'HTTP' text input.

## CherryPy ##

Use [CherryPy](http://www.cherrypy.org/) web framework to serve the example over http with the following command:
```
python echo/python/cp_server.py
```

## Twisted Example ##
Use [Twisted](http://twistedmatrix.com/trac/) web framework to serve the example over http with the following command:
```
twistd -noy echo/python/twisted_server.tac
```

## WSGI Example ##

Use simple WSGI to serve the example over http with the following command:
```
python echo/python/wsgi_server.py
```

The WSGI example does not serve the Flash file, so you will have to manually open the file in your browser:
```
echo/flex/deploy/red5Test.html
```