# HelloWorld Example #

This example demonstrates a very simple service and a Flex client.

The remote method can be invoked using NetConnection or RemoteObject.

The example is located in SVN within the [examples/hello\_world](http://code.google.com/p/amfast/source/browse/trunk/examples/hello_world) directory

The example has scripts for serving the application via [CherryPy](http://www.cherrypy.org/), [Twisted Web](http://twistedmatrix.com/trac/), or WSGI.

Start the server and point your browser to http://localhost:8000

## CherryPy ##

Use [CherryPy](http://www.cherrypy.org/) web framework to serve the example over http with the following command:
```
python hello_world/python/cp_server.py
```

## Twisted Example ##
Use [Twisted](http://twistedmatrix.com/trac/) web framework to serve the example over http with the following command:
```
twistd -noy hello_world/python/twisted_server.tac
```

## WSGI Example ##

Use simple WSGI to serve the example over http with the following command:
```
python hello_world/python/wsgi_server.py
```

The WSGI example does not serve the Flash file, so you will have to manually open the file in your browser:
```
hello_world/flex/deploy/hello_world.html
```

## Django Example ##

Use the Django Development server to serve the example over http with the following command:

```
python hello_world/django_amf_example/manage.py runserver 8000
```