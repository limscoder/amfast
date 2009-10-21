from django import http

import amfast
from channel import HttpChannel, ChannelError

class DjangoChannel(HttpChannel):
    """A channel that works with Django."""

    # Attribute that holds Django's
    # request object, so that it can 
    # be accessed from a target.
    DJANGO_REQUEST = '_django_request'

    def __call__(self, http_request):
        if http_request.method != 'POST':
            return http.HttpResponseNotAllowed(['POST'])

        try:
            request_packet = self.decode(http_request.raw_post_data)
            setattr(request_packet, self.DJANGO_REQUEST, http_request)
        except amfast.AmFastError, exc:
            return http.HttpResponseBadRequest(mimetype='text/plain', content=self.getBadEncodingMsg())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            return http.HttpResponseServerError(mimetype='text/plain', content=self.getBadServerMsg())

        try:
            response_packet = self.invoke(request_packet)
            raw_response = self.encode(response_packet)

            http_response = http.HttpResponse(mimetype=self.CONTENT_TYPE)
            http_response['Content-Length'] = str(len(raw_response))
            http_response.write(raw_response)
            return http_response
        except amfast.AmFastError, exc:
            return http.HttpResponseServerError(mimetype='text/plain', content=self.getBadServerMsg())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            return http.HttpResponseServerError(mimetype='text/plain', content=self.getBadServerMsg())

# TODO: StreamingDjangoChannel!!
