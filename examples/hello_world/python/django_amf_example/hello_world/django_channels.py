import sys
import os

from amfast.remoting.channel import ChannelSet
from amfast.remoting.django_channel import DjangoChannel

sys.path.append(os.path.join('..', '..'))

import utils

channel_set = ChannelSet()
rpc_channel = DjangoChannel('amf')
channel_set.mapChannel(rpc_channel)
utils.setup_channel_set(channel_set)
