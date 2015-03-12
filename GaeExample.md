# Gae Example #

This example demonstrates using Producer/Consumer messaging with HTTP polling running on the Google App Engine platform.

[Example demo](http://amfastchat.appspot.com/flash/chat.html)

The example is located in SVN within the [examples/gae](http://code.google.com/p/amfast/source/browse/#svn/trunk/examples/gae) directory.

## Setup GAE ##

  * [Download](http://code.google.com/appengine/downloads.html#Google_App_Engine_SDK_for_Python) and install the Google App Engine SDK.

## Setup Application ##

  * Check out the AmFast source code from http://code.google.com/p/amfast/source/browse/#svn/trunk/ into a folder named 'AmFast' with the following command:
```
svn checkout http://amfast.googlecode.com/svn/trunk/ AmFast
```

  * Python extensions cannot be compiled for Google App Engine. You will need to use a pure-python encoder and decoder.
    * Download and extract the latest production version of [PyAmf](http://pyamf.org/wiki/Download)
    * Copy the 'pyamf' folder from the PyAmf distribution into the 'AmFast/examples/gae' folder.

## Run the app ##
  * Use the following command to launch the app:
```
google_appengine/dev_appserver.py AmFast/examples/gae/
```
  * Point your browser to http://localhost:8080/flash/chat.html