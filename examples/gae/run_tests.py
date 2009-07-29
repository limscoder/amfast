"""Runs GAE specific tests.

From: http://www.nearinfinity.com/blogs/steven_farley/unit_testing_google_app_engine.html
"""

import google.appengine.tools
import unittest
import sys
import wsgiref.handlers
from google.appengine.ext import webapp

from tests import gae_test

class TestSuiteHandler(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("=======\n Tests \n=======\n\n")
        runner = unittest.TextTestRunner(self.response.out).run(gae_test.suite())

def main():
      application = webapp.WSGIApplication([('/run_tests', TestSuiteHandler)], debug=True)
      wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()
