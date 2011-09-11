import types
import threading

from django import http

import amfast
from amfast.remoting import Packet
import amfast.remoting.flex_messages as messaging
from amfast.remoting.channel import HttpChannel, ChannelError

def django_response_wrapper(func):
    '''
    A decorator which wrap a bare response to a DjangoResopnse  
    '''
    def _(channel, django_request):
        response_packet = func(channel, django_request)
        if response_packet is None:
            return http.HttpResponse(mimetype = channel.CONTENT_TYPE)
        elif type(response_packet) is types.GeneratorType:
            http_response = http.HttpResponse(content=response_packet, mimetype=channel.CONTENT_TYPE)
            return http_response
        else:
            raise ChannelError('Invalid response type.')
    return _

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

class StreamingDjangoChannel(DjangoChannel):
    """Experimental support for streaming with Django."""

    def __init__(self, name, max_connections=-1, endpoint=None,
        wait_interval=0, heart_interval=30000):
        DjangoChannel.__init__(self, name, max_connections=max_connections,
            endpoint=endpoint, wait_interval=wait_interval)
            
        self.heart_interval = heart_interval
        
    def __call__(self, http_request):
        if http_request.META['CONTENT_TYPE'] == self.CONTENT_TYPE:
            return DjangoChannel.__call__(self, http_request)
            
        try:
            body = http_request.raw_post_data
            msg = messaging.StreamingMessage()
            msg.parseBody(body)
            #django has a well wrapped http_request object which contents all the wsgi options
            msg.parseParams(http_request.META['QUERY_STRING'])
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            
        if msg.operation == msg.OPEN_COMMAND:
            return self.startStream(msg)
            
        elif msg.operation == msg.CLOSE_COMMAND:
            return self.stopStream(msg)
            
        raise ChannelError('Http streaming operation unknown: %s' % msg.operation)
    
    @django_response_wrapper
    def startStream(self, msg):
        try: 
            connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            raise ChannelError('Http streaming operation unknown: %s' % msg.operation)
        
        try:
            timer = threading.Timer(float(self.heart_interval) / 1000, self.beat, (connection, ))
            timer.daemon = True
            timer.start()

            inited = False
            event = threading.Event()
            connection.setNotifyFunc(event.set)
            poll_secs = float(self.poll_interval) / 1000
            while True:
                if connection.connected is False:
                    msg = messaging.StreamingMessage.getDisconnectMsg()
                    try:
                        yield messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
                    finally:
                        # Client may have already disconnected
                        return 
                        
                if inited is False:
                    # Send acknowledge message
                    response = msg.acknowledge()
                    response.body = connection.id

                    bytes = messaging.StreamingMessage.prepareMsg(response, self.endpoint)
                    inited = True

                    bytes += chr(messaging.StreamingMessage.NULL_BYTE) * self.KICKSTART_BYTES
                    yield bytes
                    
                if self.channel_set.notify_connections is True:
                    # Block until notification of new message
                    event.wait()
                else:
                    # Block until poll_interval is reached
                    event.wait(poll_secs)
                    
                # Message has been published,
                # or it's time for a heart beat

                # Remove notify_func so that
                # New messages don't trigger event.
                connection.unSetNotifyFunc()

                msgs = self.channel_set.subscription_manager.pollConnection(connection)
                
                if len(msgs) > 0:
                    while len(msgs) > 0:
                        # Dispatch all messages to client
                        for msg in msgs:
                            try:
                                bytes = messaging.StreamingMessage.prepareMsg(msg, self.endpoint)
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except Exception, exc:
                                amfast.log_exc(exc)
                                self.channel_set.disconnect(connection)
                                break

                            try:
                                yield bytes
                                # return bytes
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except:
                                # Client has disconnected
                                self.channel_set.disconnect(connection)
                                return 
                        msgs = self.channel_set.subscription_manager.pollConnection(connection)
                else:
                    # Send heart beat
                    try:
                        yield chr(messaging.StreamingMessage.NULL_BYTE)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        # Client has disconnected
                        self.channel_set.disconnect(connection)
                        return 

                # Create new event to trigger new messages or heart beats
                event = threading.Event()
                connection.setNotifyFunc(event.set)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, exc:
            amfast.log_exc(exc)
            self.channel_set.disconnect(connection)
            return 
            
            
    @django_response_wrapper
    def stopStream(self, msg):
        """Stop a streaming connection."""

        connection = self.channel_set.connection_manager.getConnection(msg.headers.get(msg.FLEX_CLIENT_ID_HEADER))
        connection.disconnect()
        if hasattr(connection, "notify_func") and connection.notify_func is not None:
            connection.notify_func()
    
    @django_response_wrapper
    def beat(self, connection):
        """Send a heart beat."""

        if hasattr(connection, "notify_func") and connection.notify_func is not None:
            connection.notify_func()
        else:
            return

        # Create timer for next beat
        timer = threading.Timer(float(self.heart_interval) / 1000, self.beat, (connection, ))
        timer.daemon = True
        timer.start()
