import zmq
import time
import struct
import socket
import uuid
import logging
import sys

# local modules
from . import __version_info__
from . import zbeacon
from . import zhelper
from .zactor import ZActor
from .zsocket import ZSocket
from .pyre_node import PyreNode
from .pyre_event import PyreEvent

logger = logging.getLogger(__name__)

try:
    raw_input          # Python 2
except NameError:
    raw_input = input  # Python 3


class Pyre(object):

    def __init__(self, name=None, ctx=None, *args, **kwargs):
        """Constructor, creates a new Zyre node. Note that until you start the
        node it is silent and invisible to other nodes on the network.
        The node name is provided to other nodes during discovery. If you
        specify NULL, Zyre generates a randomized node name from the UUID.

        Args:
            name (str): The name of the node

        Kwargs:
            ctx: PyZMQ Context, if not specified a new context will be created
        """
        super(Pyre, self).__init__(*args, **kwargs)
        ctx = kwargs.get('ctx')
        if ctx == None:
            ctx = zmq.Context()
        self._ctx = ctx
        self._uuid = None
        self._name = name
        self.verbose = False
        self.inbox, self._outbox = zhelper.zcreate_pipe(self._ctx)

        # Start node engine and wait for it to be ready
        self.actor = ZActor(self._ctx, PyreNode, self._outbox)
        # Send name, if any, to node backend
        if (self._name):
            self.actor.send_unicode("SET NAME", zmq.SNDMORE)
            self.actor.send_unicode(self._name)

    #def __del__(self):
        # We need to explicitly destroy the actor
        # to make sure our node thread is stopped
        #self.actor.destroy()

    def __bool__(self):
        "Determine whether the object is valid by converting to boolean" # Python 3
        return True  #TODO

    def __nonzero__(self):
        "Determine whether the object is valid by converting to boolean" # Python 2
        return True  #TODO

    def uuid(self):
        """Return our node UUID string, after successful initialization"""
        if not self._uuid:
            self.actor.send_unicode("UUID")
            self._uuid = uuid.UUID(bytes=self.actor.recv())
        return self._uuid

    # Return our node name, after successful initialization
    def name(self):
        """Return our node name, after successful initialization"""
        if not self._name:
            self.actor.send_unicode("NAME")
            self._name = self.actor.recv().decode('utf-8')
        return self._name

    # Not in Zyre api
    def set_name(self, name):
        logger.warning("DEPRECATED: set name in constructor, this method will be removed!")
        self.actor.send_unicode("SET NAME", zmq.SNDMORE)
        self.actor.send_unicode(name)

    def set_header(self, key, value):
        """Set node header; these are provided to other nodes during discovery
        and come in each ENTER message."""
        self.actor.send_unicode("SET HEADER", flags=zmq.SNDMORE)
        self.actor.send_unicode(key, flags=zmq.SNDMORE)
        self.actor.send_unicode(value)

    def set_verbose(self):
        """Set verbose mode; this tells the node to log all traffic as well as
        all major events."""
        self.actor.send_unicode("SET VERBOSE")

    def set_port(self, port_nbr):
        """Set UDP beacon discovery port; defaults to 5670, this call overrides
        that so you can create independent clusters on the same network, for
        e.g. development vs. production. Has no effect after zyre_start()."""
        self.actor.send_unicode("SET PORT", zmq.SNDMORE)
        self.actor.send(port_nbr)

    def set_interval(self, interval):
        """Set UDP beacon discovery interval, in milliseconds. Default is instant
        beacon exploration followed by pinging every 1,000 msecs."""
        self.actor.send_unicode("SET INTERVAL", zmq.SNDMORE)
        self.actor.send_unicode(interval)

    def set_interface(self, value):
        """Set network interface for UDP beacons. If you do not set this, CZMQ will
        choose an interface for you. On boxes with several interfaces you should
        specify which one you want to use, or strange things can happen."""
        logging.debug("set_interface not implemented") #TODO

    # TODO: check args from zyre
    def set_endpoint(self, format, *args):
        """By default, Zyre binds to an ephemeral TCP port and broadcasts the local
        host name using UDP beaconing. When you call this method, Zyre will use
        gossip discovery instead of UDP beaconing. You MUST set-up the gossip
        service separately using zyre_gossip_bind() and _connect(). Note that the
        endpoint MUST be valid for both bind and connect operations. You can use
        inproc://, ipc://, or tcp:// transports (for tcp://, use an IP address
        that is meaningful to remote as well as local nodes). Returns 0 if
        the bind was successful, else -1."""
        self.actor.send_unicode("SET ENDPOINT", zmq.SNDMORE)
        self.actor.send_unicode(format)

    # TODO: We haven't implemented gossiping yet
    #def gossip_bind(self, format, *args):
    #def gossip_connect(self, format, *args):

    def start(self):
        """Start node, after setting header values. When you start a node it
        begins discovery and connection. Returns 0 if OK, -1 if it wasn't
        possible to start the node."""
        self.actor.send_unicode("START")
        # the backend will signal back
        self.actor.resolve().wait()

    def stop(self):
        """Stop node; this signals to other peers that this node will go away.
        This is polite; however you can also just destroy the node without
        stopping it."""
        self.actor.send_unicode("STOP", flags=zmq.DONTWAIT)
        # the backend will signal back
        self.actor.resolve().wait()
        self.actor.destroy()

    # Receive next message from node
    def recv(self):
        """Receive next message from network; the message may be a control
        message (ENTER, EXIT, JOIN, LEAVE) or data (WHISPER, SHOUT).
        """
        return self.inbox.recv_multipart()

    def join(self, group):
        """Join a named group; after joining a group you can send messages to
        the group and all Zyre nodes in that group will receive them."""
        self.actor.send_unicode("JOIN", flags=zmq.SNDMORE)
        self.actor.send_unicode(group)

    def leave(self, group):
        """Leave a group"""
        self.actor.send_unicode("LEAVE", flags=zmq.SNDMORE)
        self.actor.send_unicode(group)

    # Send message to single peer; peer ID is first frame in message
    def whisper(self, peer, msg_p):
        """Send message to single peer, specified as a UUID string
        Destroys message after sending"""
        self.actor.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self.actor.send(peer.bytes, flags=zmq.SNDMORE)
        if isinstance(msg_p, list):
            self.actor.send_multipart(msg_p)
        else:
            self.actor.send(msg_p)

    def shout(self, group, msg_p):
        """Send message to a named group
        Destroys message after sending"""
        self.actor.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self.actor.send_unicode(group, flags=zmq.SNDMORE)
        if isinstance(msg_p, list):
            self.actor.send_multipart(msg_p)
        else:
            self.actor.send(msg_p)

    # TODO: checks args from zyre
    def whispers(self, peer, format, *args):
        """Send formatted string to a single peer specified as UUID string"""
        self.actor.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self.actor.send(peer.bytes, flags=zmq.SNDMORE)
        self.actor.send_unicode(format)

    def shouts(self, group, format, *args):
        """Send formatted string to a named group"""
        self.actor.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self.actor.send_unicode(group, flags=zmq.SNDMORE)
        self.actor.send_unicode(format)

    def peers(self):
        """Return list of current peer ids."""
        self.actor.send_unicode("PEERS")
        peers = self.actor.recv_pyobj()
        return peers

    def peers_by_group(self, group):
        """Return list of current peer ids."""
        self.actor.send_unicode("PEERS BY GROUP", flags=zmq.SNDMORE)
        self.actor.send_unicode(group)
        peers_by_group = self.actor.recv_pyobj()
        return peers_by_group

    def endpoint(self):
        """Return own endpoint"""
        self.actor.send_unicode("ENDPOINT")
        endpoint = self.actor.recv_unicode()
        return endpoint

    def recent_events(self):
        """Iterator that yields recent `PyreEvent`s"""
        while self.socket().get(zmq.EVENTS) & zmq.POLLIN:
            yield PyreEvent(self)

    def events(self):
        """Iterator that yields `PyreEvent`s indefinitely"""
        while True:
            yield PyreEvent(self)

    # --------------------------------------------------------------------------
    # Return the name of a connected peer. Caller owns the
    # string.
    # DEPRECATED: This is dropped in Zyre api. You receive names through events
    def get_peer_name(self, peer):
        logger.warning("get_peer_name() is deprecated, will be removed")
        self.actor.send_unicode("PEER NAME", zmq.SNDMORE)
        self.actor.send(peer.bytes)
        name = self.actor.recv_unicode()
        return name

    def peer_address(self, peer):
        """Return the endpoint of a connected peer."""
        self.actor.send_unicode("PEER ENDPOINT", zmq.SNDMORE)
        self.actor.send(peer.bytes)
        adr = self.actor.recv_unicode()
        return adr

    def peer_header_value(self, peer, name):
        """Return the value of a header of a conected peer.
        Returns null if peer or key doesn't exist."""
        self.actor.send_unicode("PEER HEADER", zmq.SNDMORE)
        self.actor.send(peer.bytes, zmq.SNDMORE)
        self.actor.send_unicode(name)
        value = self.actor.recv_unicode()
        return value

    def peer_headers(self, peer):
        """Return the value of a header of a conected peer.
        Returns null if peer or key doesn't exist."""
        self.actor.send_unicode("PEER HEADERS", zmq.SNDMORE)
        self.actor.send(peer.bytes)
        headers = self.actor.recv_pyobj()
        return headers

    def own_groups(self):
        """Return list of currently joined groups."""
        self.actor.send_unicode("OWN GROUPS");
        groups = self.actor.recv_pyobj()
        return groups

    def peer_groups(self):
        """Return list of groups known through connected peers."""
        self.actor.send_unicode("PEER GROUPS")
        groups = self.actor.recv_pyobj()
        return groups

    # Return node socket, for direct polling of socket
    def socket(self):
        """Return socket for talking to the Zyre node, for polling"""
        return self.inbox

    @staticmethod
    def version():
        return __version_info__

def chat_task(ctx, pipe):
    n = Pyre(ctx=ctx)
    n.join("CHAT")
    n.start()

    poller = zmq.Poller()
    poller.register(pipe, zmq.POLLIN)
    poller.register(n.socket(), zmq.POLLIN)
    while(True):
        items = dict(poller.poll())
        if pipe in items:
            message = pipe.recv()
            if message == '$TERM':
                break
            logger.debug("CHAT_TASK: {0}".format(message))
            n.shout("CHAT", message)

        if n.socket() in items:
            event = PyreEvent(n)

            logger.debug("NODE_MSG TYPE: {0}".format(event.type))
            logger.debug("NODE_MSG PEER: {0}".format(event.peer_uuid))

            if event.type == "SHOUT":
                logger.debug("NODE_MSG GROUP: {0}".format(event.group))

            logger.debug("NODE_MSG CONT: {0}".format(event.msg))
    n.stop()

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger('__main__').setLevel(logging.DEBUG)

    ctx = zmq.Context()
    chat_pipe = zhelper.zthread_fork(ctx, chat_task)
    while True:
        try:
            msg = raw_input()
            chat_pipe.send_string(msg)
        except (KeyboardInterrupt, SystemExit):
            chat_pipe.send_string('$TERM')
            break
    logger.debug("Exiting")
