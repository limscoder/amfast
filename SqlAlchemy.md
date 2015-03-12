# SqlAlchemy Example #

This example demonstrates persisting data with [SqlLite](http://www.sqlite.org/) and [SqlAlchemy](http://www.sqlalchemy.org/).

[Example demo](http://ccp.arl.arizona.edu/dthompso/amfast/contacts_demo.htm)

The example is located in SVN within the [examples/addressbook](http://code.google.com/p/amfast/source/browse/trunk/examples/addressbook) directory

The example has scripts for serving the application via [CherryPy](http://www.cherrypy.org/), [Twisted Web](http://twistedmatrix.com/trac/), or WSGI.

Start the server and point your browser to http://localhost:8000

## CherryPy ##

Use [CherryPy](http://www.cherrypy.org/) web framework to serve the example contact manager over http with the following command:
```
twistd -noy addressbook/python/cp_server.py
```

## Twisted Example ##
Use [Twisted](http://twistedmatrix.com/trac/) web framework to serve the example contact manager over http with the following command:
```
python addressbook/python/twisted_server.tac
```

## WSGI Example ##

Use simple WSGI to serve the example contact manager over http with the following command:
```
python addressbook/python/wsgi_server.py
```

The WSGI example does not serve the Flash file, so you will have to manually open the file in your browser:
```
addressbook/flex/deploy/addressbook.html
```