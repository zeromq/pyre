import zmq
import time
import struct
import socket
import uuid
import logging
import sys

# local modules
from . import zbeacon
from . import zhelper
from .zactor import ZActor
from .zsocket import ZSocket
from .pyre_node import PyreNode

logger = logging.getLogger(__name__)


class Pyre(object):

    def __init__(self, ctx=zmq.Context()):
        self._ctx = ctx
        self._uuid = None
        self._name = None
        self.verbose = False
        self.inbox, self._outbox = zhelper.zcreate_pipe(self._ctx)

        # Start node engine and wait for it to be ready
        self.actor = ZActor(self._ctx, PyreNode, self._outbox)
        # Send name, if any, to node ending 
        if (self._name):
            self.actor.send_unicode("SET NAME", zmq.SNDMORE)
            self.actor.send_unicode(self._name)

    #def __del__(self):
        # We need to explicitly destroy the actor 
        # to make sure our node thread is stopped
        #self.actor.destroy()

    # Return our node UUID, after successful initialization
    def uuid(self):
        if not self._uuid:
            self.actor.send_unicode("UUID")
            self._uuid = uuid.UUID(bytes=self.actor.recv())
        return self._uuid

    # Return our node name, after successful initialization
    def name(self):
        if not self._name:
            self.actor.send_unicode("NAME")
            self._name = self.actor.recv().decode('utf-8')
        return self._name

    # Not in Zyre api
    def set_name(self, name):
        self.actor.send_unicode("SET NAME", zmq.SNDMORE)
        self.actor.send_unicode(name)

    # Set node header value
    def set_header(self, key, value):
        self.actor.send_unicode("SET HEADER", flags=zmq.SNDMORE)
        self.actor.send_unicode(key, flags=zmq.SNDMORE)
        self.actor.send_unicode(value)

    def set_verbose(self):
        self.actor.send_unicode("SET VERBOSE")

    def set_port(self, port_nbt):
        self.actor.send_unicode("SET PORT", zmq.SNDMORE)
        self.actor.send(port_nbr)

    def set_interval(self, interval):
        self.actor.send_unicode("SET INTERVAL", zmq.SNDMORE)
        self.actor.send_unicode(interval)

    def set_interface(self, value):
        logging.debug("set_interface not implemented")

    # TODO: check args from zyre
    def set_endpoint(self, format, *args):
        self.actor.send_unicode("SET ENDPOINT", zmq.SNDMORE)
        self.actor.send_unicode(format)

    # TODO: We haven't implemented gossiping yet
    #def gossip_bind(self, format, *args):
    #def gossip_connect(self, format, *args):

    def start(self):
        self.actor.send_unicode("START")
        # the backend will signal back
        self.actor.resolve().wait()

    def stop(self):
        self.actor.send_unicode("STOP", flags=zmq.DONTWAIT)
        # the backend will signal back
        self.actor.resolve().wait()
        self.actor.destroy()

    # Receive next message from node
    def recv(self):
        return self.inbox.recv_multipart()

    # Join a group
    def join(self, group):
        self.actor.send_unicode("JOIN", flags=zmq.SNDMORE)
        self.actor.send_unicode(group)

    # Leave a group
    def leave(self, group):
        self.actor.send_unicode("LEAVE", flags=zmq.SNDMORE)
        self.actor.send_unicode(group)

    # Send message to single peer; peer ID is first frame in message
    def whisper(self, peer, msg_p):
        self.actor.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self.actor.send(peer.bytes, flags=zmq.SNDMORE)
        if isinstance(msg_p, list):
            self.actor.send_multipart(msg_p)
        else:
            self.actor.send(msg_p)

    # Send message to a group of peers
    def shout(self, group, msg_p):
        self.actor.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self.actor.send_unicode(group, flags=zmq.SNDMORE)
        if isinstance(msg_p, list):
            self.actor.send_multipart(msg)
        else:
            self.actor.send(msg_p)

    # Send message to single peer; peer ID is first frame in message
    # TODO: checks args from zyre
    def whispers(self, peer, format, *args):
        self.actor.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self.actor.send(peer.bytes, flags=zmq.SNDMORE)
        self.actor.send_unicode(format)

    def shouts(self, group, format, *args):
        self.actor.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self.actor.send_unicode(group, flags=zmq.SNDMORE)
        self.actor.send_unicode(format)

    #  --------------------------------------------------------------------------
    #  Return list of current peers. The caller owns this list and should
    #  destroy it when finished with it.
    def peers(self):
        self.actor.send_unicode("PEERS")
        peers = self.actor.recv_pyobj()
        return peers

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

    # --------------------------------------------------------------------------
    # Return the endpoint of a connected peer. Caller owns the
    # string.
    def peer_address(self, peer):
        self.actor.send_unicode("PEER ENDPOINT", zmq.SNDMORE)
        self.actor.send(peer.bytes)
        adr = self.actor.recv_unicode()
        return adr

    #  --------------------------------------------------------------------------
    #  Return the value of a header of a conected peer. 
    #  Returns null if peer or key doesn't exist.
    def peer_header_value(self, peer, name):
        self.actor.send_unicode("PEER HEADER", zmq.SNDMORE)
        self.actor.send(peer.bytes, zmq.SNDMORE)
        self.actor.send_unicode(name)
        value = self.actor.recv_unicode()
        return value

    #  --------------------------------------------------------------------------
    #  Return zlist of currently joined groups.
    def own_groups(self):
        self.actor.send_unicode("OWN GROUPS");
        groups = self.actor.recv_pyobj()
        return groups

    #  --------------------------------------------------------------------------
    #  Return zlist of groups known through connected peers. 
    def peer_groups(self):
        self.actor.send_unicode("PEER GROUPS")
        groups = self.actor.recv_pyobj()
        return groups

    # Return node socket, for direct polling of socket
    def socket(self):
        return self.inbox

    def version(self):
        logger.warning("version() not implemented yet")


def chat_task(ctx, pipe):
    n = Pyre(ctx)
    n.join("CHAT")

    poller = zmq.Poller()
    poller.register(pipe, zmq.POLLIN)
    poller.register(n.get_socket(), zmq.POLLIN)
    while(True):
        items = dict(poller.poll())
        if pipe in items and items[pipe] == zmq.POLLIN:
            message = pipe.recv()
            logger.debug("CHAT_TASK: {0}".format(message))
            n.shout("CHAT", message)

        if n.get_socket() in items and items[n.get_socket()] == zmq.POLLIN:
            cmds = n.get_socket().recv_multipart()

            type = cmds.pop(0)

            logger.debug("NODE_MSG TYPE: {0}".format(type))
            logger.debug("NODE_MSG PEER: {0}".format(uuid.UUID(bytes=cmds.pop(0))))

            if type.decode('utf-8') == "SHOUT":
                logger.debug("NODE_MSG GROUP: {0}".format(cmds.pop(0)))

            logger.debug("NODE_MSG CONT: {0}".format(cmds))


if __name__ == '__main__':
    ctx = zmq.Context()
    chat_pipe = zhelper.zthread_fork(ctx, chat_task)
    while True:
        try:
            msg = input()
            chat_pipe.send(msg.encode('utf_8'))
        except (KeyboardInterrupt, SystemExit):
            break

    logger.debug("Exiting")
