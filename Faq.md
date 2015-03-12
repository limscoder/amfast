# Faq #

## How do I get the encoder/decoder extensions to compile in Windows? ##

### MinGW/GCC ###
  * MinGW provides a very basic GNU environment in Windows, allowing you to use GCC.
  * This answer was provided by Warlei in a comment on my [blog](http://limscoder.blogspot.com/2009/03/amfast-022-released.html#comments).
  * It should work with Python 2.5 and 2.6.

  1. Download and install MinGW. http://sourceforge.net/project/showfiles.php?group_id=2435
  1. Add {MinGW}\bin directory to the system PATH
  1. Download and unpack AmFast source code from PyPi
  1. In the directory you've unpacked AmFast type:
    1. `python setup.py build -c mingw32`
    1. `python setup.py install`

### Visual Studio 2008 ###
  * This method should work with Python 2.6.
  * I tried this method with Visual Studio C++ 2008 Express Edition, which is a [free download from Microsoft](http://www.microsoft.com/express/vc/).

  1. Open Visual Studio.
  1. Select 'Tools->Visual Studio 2008 Command Prompt'.
  1. In the directory you've unpacked AmFast type:
    1. `python setup.py install`

### Trouble Shooting ###
  * If you experience problems compiling AmFast on Windows, you may want to take a look at some of these links.
  * http://www.zope.org/Members/als/tips/win32_mingw_modules

## How much faster is AmFast compared with PyAmf? ##
  * AmFast is anywhere from 2x to 12x quicker than cPyAmf version 0.5.1 at encoding and decoding binary AMF streams.
  * The exact difference depends on system architecture, Python version, and the type of objects in the stream.
  * Benchmarks coming soon!