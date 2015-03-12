# Real-time messaging Example #

This example demonstrates using Producer/Consumer messaging with an HTTP streaming channel to achieve real-time messaging. The application displays a circular object. A 'master' client can drag the object around the screen, and the movements of the object will be replicated to all other subscribed clients.

[Example demo](http://ccp.arl.arizona.edu/dthompso/amfast/circle_sprite_demo.htm)

The example is located in SVN within the [examples/streaming](http://code.google.com/p/amfast/source/browse/trunk/examples/streaming) directory

The example has scripts for serving the application via [CherryPy](http://www.cherrypy.org/), [Twisted Web](http://twistedmatrix.com/trac/), and [Tornado](http://www.tornadoweb.org/).

Start the server and open two browser windows to http://localhost:8000

Click the 'Subscribe' button to start receiving messages.

When the 'master' client drags the yellow circle around the screen, the new position of the circle object will be replicated to all other subscribed clients.

Click the 'Master' button to become the master client.

If you change the messaging url, you must un-subscribe and re-subscribe to start receiving messages from the new url.

## CherryPy ##

Use [CherryPy](http://www.cherrypy.org/) web framework and WSGI to serve the example with the following command:
```
python streaming/python/cp_server.py
```

## Twisted ##
Use [Twisted](http://twistedmatrix.com/trac/) web framework to serve the example with the following command:
```
twistd -noy streaming/python/twisted_server.tac
```
Point your browser to: http://localhost:8000/streaming.html.

## Tornado ##
Use Facebook's [Tornado](http://www.tornadoweb.org/) web framework to serve the example  with the following command:
```
python streaming/python/tornado_server.py
```
Point your browser to: http://localhost:8000/static/streaming.html.