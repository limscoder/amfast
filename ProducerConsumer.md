# Producer/Consumer Example #

This example demonstrates using Producer/Consumer messaging with HTTP polling and HTTP long-polling channels. The application is a very simple chat client.

[Example demo](http://ccp.arl.arizona.edu/dthompso/amfast/chat_demo.htm)

The example is located in SVN within the [examples/messaging](http://code.google.com/p/amfast/source/browse/trunk/examples/messaging) directory

The example has scripts for serving the application via [CherryPy](http://www.cherrypy.org/), [Twisted Web](http://twistedmatrix.com/trac/), and [Tornado](http://www.tornadoweb.org/).

Start the server and open two browser windows to http://localhost:8000

Click the 'Subscribe' button to start receiving messages.

Click the 'Publish' button to send a message.

When a message is published, it should appear in both browser windows.

The default 'amf' url uses polling. Change the url to 'longPoll' to use long-polling.

If you change the url, you must un-subscribe and re-subscribe to start receiving messages from the new url.

## CherryPy ##

Use [CherryPy](http://www.cherrypy.org/) web framework and WSGI to serve the example with the following command:
```
python messaging/python/cp_server.py
```

## Twisted ##
Use [Twisted](http://twistedmatrix.com/trac/) web framework to serve the example with the following command:
```
twistd -noy messaging/python/twisted_server.tac
```
Point your browser to http://localhost:8000/messaging.html.

## Tornado ##
Use Facebook's [Tornado](http://www.tornadoweb.org/) web framework to serve the example  with the following command:
```
python messaging/python/tornado_server.py
```
Point your browser to http://localhost:8000/static/messaging.html.