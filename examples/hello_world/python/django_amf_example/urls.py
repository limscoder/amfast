import os

from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^django_amf_example/', include('django_amf_example.foo.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # (r'^admin/', include(admin.site.urls)),
    (r'^$', 'django.views.generic.simple.redirect_to', {'url': '/static/hello_world.html'}),
    (r'^amf/', 'django_amf_example.hello_world.django_channels.rpc_channel'),
    (r'^static/(?P<path>.*)$', 'django.views.static.serve', {
        'document_root': os.path.join('flex', 'deploy'),
        'show_indexes': True}),
)
