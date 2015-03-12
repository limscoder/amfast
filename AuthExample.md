# Authentication Example #

This example demonstrates using authentication with AmFast.

Authentication works with both NetConnection and RemoteObject.

The example is located in SVN within the [examples/auth](http://code.google.com/p/amfast/source/browse/trunk/examples/auth) directory

The example has scripts for serving the application via [CherryPy](http://www.cherrypy.org/), [Twisted Web](http://twistedmatrix.com/trac/), or WSGI.

Start the server and point your browser to http://localhost:8000

## CherryPy ##

Use [CherryPy](http://www.cherrypy.org/) web framework to serve the example over http with the following command:
```
python auth/python/cp_server.py
```

## Twisted Example ##
Use [Twisted](http://twistedmatrix.com/trac/) web framework to serve the example over http with the following command:
```
twistd -noy auth/python/twisted_server.tac
```

## WSGI Example ##

Use simple WSGI to serve the example over http with the following command:
```
python auth/python/wsgi_server.py
```

The WSGI example does not serve the Flash file, so you will have to manually open the file in your browser:
```
auth/flex/deploy/auth.html
```