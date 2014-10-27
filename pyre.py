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
from .zsocket import ZSocket
from .zre_msg import ZreMsg
from .pyre_peer import PyrePeer
from .pyre_group import PyreGroup

BEACON_VERSION = 1
ZRE_DISCOVERY_PORT = 5670
REAP_INTERVAL = 1.0  # Once per second

logger = logging.getLogger(__name__)


class Pyre(object):

    def __init__(self, ctx=zmq.Context()):
        self._ctx = ctx
        self.uuid = None
        self.name = None
        self.verbose = False
        self._pipe = zhelper.zthread_fork(self._ctx, PyreNode)

    # Return our node UUID, after successful initialization
    def get_uuid(self):
        if not self.uuid:
            self._pipe.send_unicode("UUID")
            self.uuid = uuid.UUID(bytes=self._pipe.recv())
        return self.uuid

    # Return our node name, after successful initialization
    def get_name(self):
        if not self.name:
            self._pipe.send_unicode("NAME")
            self.name = self._pipe.recv().decode('utf-8')
        return self.name

    def set_name(self, name):
        self._pipe.send_unicode("SET NAME", zmq.SNDMORE)
        self._pipe.send_unicode(name)

    # Set node header value
    def set_header(self, key, value):
        self._pipe.send_unicode("SET HEADER", flags=zmq.SNDMORE)
        self._pipe.send_unicode(key, flags=zmq.SNDMORE)
        self._pipe.send_unicode(value)

    def set_verbose(self):
        self._pipe.send_unicode("SET VERBOSE")

    def set_port(self, port):
        self._pipe.send_unicode("SET PORT", zmq.SNDMORE)
        self._pipe.send(port)

    def set_interval(self, interval):
        self._pipe.send_unicode("SET INTERVAL", zmq.SNDMORE)
        self._pipe.send_unicode(interval)

    def start(self):
        self._pipe.send_unicode("START")
        # TODO wait signal

    def stop(self):
        self._pipe.send_unicode("STOP", flags=zmq.DONTWAIT)

    # Receive next message from node
    def recv(self):
        return self._pipe.recv()

    # Join a group
    def join(self, group):
        self._pipe.send_unicode("JOIN", flags=zmq.SNDMORE)
        self._pipe.send_unicode(group)

    # Leave a group
    def leave(self, group):
        self._pipe.send_unicode("LEAVE", flags=zmq.SNDMORE)
        self._pipe.send_unicode(group)

    # Send message to single peer; peer ID is first frame in message
    def whisper(self, peer, msg):
        self._pipe.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self._pipe.send(peer.bytes, flags=zmq.SNDMORE)
        if isinstance(msg, list):
            self._pipe.send_multipart(msg)
        else:
            self._pipe.send(msg)

    # Send message to a group of peers
    def shout(self, group, msg):
        self._pipe.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self._pipe.send_unicode(group, flags=zmq.SNDMORE)
        if isinstance(msg, list):
            self._pipe.send_multipart(msg)
        else:
            self._pipe.send(msg)

    # Send message to single peer; peer ID is first frame in message
    def whispers(self, peer, msg):
        self._pipe.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self._pipe.send(peer.bytes, flags=zmq.SNDMORE)
        self._pipe.send_unicode(msg)

    def shouts(self, group, msg):
        self._pipe.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self._pipe.send_unicode(group, flags=zmq.SNDMORE)
        self._pipe.send_unicode(msg)

    # Return node socket, for polling
    def get_socket(self):
        return self._pipe

    # Set node header value
    def set_header(self, name, value, *args):
        self._pipe.send_unicode("SET", flags=zmq.SNDMORE)
        self._pipe.send_unicode(name, flags=zmq.SNDMORE)
        self._pipe.send_unicode(value, flags=zmq.SNDMORE)


class PyreNode(object):

    def __init__(self, ctx, pipe, *args):
        self._ctx = ctx
        self._pipe = pipe
        self._terminated = False
        self.status = 0
        self.bound = False
        self.inbox = ctx.socket(zmq.ROUTER)
        try:
            self.inbox.setsockopt(zmq.ROUTER_HANDOVER, 1)
        except AttributeError as e:
            logging.warning("can't set ROUTER_HANDOVER, probably old zmq version")
        self.outbox = ZSocket(self._ctx, zmq.DEALER)
        self.poller = zmq.Poller()
        self.poller.register(self._pipe, zmq.POLLIN)
        self.beacon_port = ZRE_DISCOVERY_PORT
        self.interval = 0       # Use default
        self.identity = uuid.uuid4()

        self.peers = {}
        self.peer_groups = {}
        self.own_groups = {}
        self.headers = {}
        self.endpoint = ""
        # Default name for node is first 6 characters of UUID:
        self.name = str(self.identity)[:6]
        self.start()
        self.run()

    # def __del__(self):
        # destroy beacon

    def start(self):
        # TODO: If application didn't bind explicitly, we grab an ephemeral port
        # on all available network interfaces. This is orthogonal to
        # beaconing, since we can connect to other peers and they will
        # gossip our endpoint to others.
        if not self.bound:
            self.port = self.inbox.bind_to_random_port("tcp://*")
            if self.port < 0:
                # Die on bad interface or port exhaustion
                logging.critical("Random port assignment for incoming messages failed. Exiting.")
                sys.exit(-1)
            else:
                self.bound = True

        if self.beacon_port:
            self.beacon = zbeacon.ZBeacon(self._ctx, self.beacon_port)
        if self.interval:
            self.beacon.set_interval(self.interval)
      
        # Our own host endpoint is provided by the beacon
        self.endpoint = "tcp://%s:%d" %(self.beacon.get_hostname(), self.port)

        # TODO: how do we set the header of the beacon?
        # line 299 zbeacon.c
        # Set broadcast/listen beacon
        transmit = struct.pack('cccb16sH', b'Z', b'R', b'E',
                               BEACON_VERSION, self.identity.bytes,
                               socket.htons(self.port))
        self.beacon.noecho()
        self.beacon.publish(transmit)
        # construct the header filter  (to discard none zre messages)
        filter = struct.pack("ccc", b'Z', b'R', b'E')
        self.beacon.subscribe(filter)

        self.poller.register(self.beacon.get_socket(), zmq.POLLIN)
        self.poller.register(self.inbox, zmq.POLLIN)
        logger.debug("Node identity: {0}".format(self.identity))

    def stop(self):
        if self.beacon:
            stop_transmit = struct.pack('cccb16sH', b'Z',b'R',b'E', 
                                   BEACON_VERSION, self.identity.bytes, 
                                   socket.htons(0))
            self.beacon.publish(stop_transmit)
            # Give time for beacon to go out
            time.sleep(0.001)
        self.poller.unregister(self.beacon.get_socket())

        #self.port = endpoint.split(':')[2]
        #self.bound = True
        #self.beacon_port = 0

    def bind(self, endpoint):
        print("Not implemented")

    # Send message to all peers
    def send_peer(self, peer, msg):
        peer.send(msg)

    def purge_peer(self, peer, endpoint):
        if (peer.get_endpoint() == endpoint):
            peer.disconnect()

    def remove_peer(self, peer):
        # TODO: we might want to first check if we even know the peer?
        self._pipe.send_unicode("EXIT", zmq.SNDMORE)
        self._pipe.send(peer.get_identity().bytes, zmq.SNDMORE)
        self._pipe.send_unicode(peer.get_name())
        # If peer has really vanished, expire it (delete)
        for grp in self.peer_groups.values():
            self.delete_peer(peer, grp)
        self.peers.pop(peer.get_identity())

    # Find or create peer via its UUID string
    def require_peer(self, identity, endpoint):
        #  Purge any previous peer on same endpoint
        p = self.peers.get(identity)
        if not p:
            # Purge any previous peer on same endpoint
            for peer_id, peer in self.peers.copy().items():
                self.purge_peer(peer, endpoint)

            p = PyrePeer(self._ctx, identity)
            self.peers[identity] = p
            p.connect(self.identity, endpoint)
            m = ZreMsg(ZreMsg.HELLO)
            m.set_endpoint(self.endpoint)
            m.set_groups(self.own_groups.keys())
            m.set_status(self.status)
            m.set_name(self.name)
            m.set_headers(self.headers)
            p.send(m)

            # Now tell the caller about the peer
            self._pipe.send_unicode("ENTER", zmq.SNDMORE)
            self._pipe.send(identity.bytes, zmq.SNDMORE)
            self._pipe.send_unicode(self.name)
        return p

    # Find or create group via its name
    def require_peer_group(self, groupname):
        grp = self.peer_groups.get(groupname)
        if not grp:
            grp = PyreGroup(groupname)
            self.peer_groups[groupname] = grp
        return grp

    def join_peer_group(self, peer, groupname):
        grp = self.require_peer_group(groupname)
        grp.join(peer)
        # Now tell the caller about the peer joined group
        self._pipe.send_unicode("JOIN", flags=zmq.SNDMORE)
        self._pipe.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
        self._pipe.send_unicode(peer.get_name(), flags=zmq.SNDMORE)
        self._pipe.send_unicode(groupname)
        return grp

    def leave_peer_group(self, peer, groupname):
        # Tell the caller about the peer joined group
        self._pipe.send_unicode("LEAVE", flags=zmq.SNDMORE)
        self._pipe.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
        self._pipe.send_unicode(peer.get_name(), flags=zmq.SNDMORE)
        self._pipe.send_unicode(groupname)
        # Now remove the peer from the group
        grp = self.require_peer_group(groupname)
        grp.leave(peer)

    # Here we handle the different control messages from the front-end
    def recv_api(self):
        request = self._pipe.recv_multipart()
        command = request.pop(0).decode('UTF-8')
        if command == "SET NAME":
            self.name = request.pop(0).decode('UTF-8')
        elif command == "SET HEADER":
            header_name = request.pop(0).decode('UTF-8')
            header_value = request.pop(0).decode('UTF-8')
            self.headers.update({header_name: header_value})
        elif command == "SET VERBOSE":
            self.verbose = True
        elif command == "SET PORT":
            self.beacon_port = int(request.pop(0))
        elif command == "SET INTERVAL":
            self.interval = int(request.pop(0))
        elif command == "UUID":
            self._pipe.send(self.identity)
        elif command == "NAME":
            self._pipe.send_unicode(self.name)
        elif command == "BIND":
            # TODO: Needs a wait-signal
            endpoint = request.pop(0).decode('UTF-8')
            self.bind(endpoint)
        elif command == "CONNECT":
            # TODO: Needs a wait-signal
            endpoint = request.pop(0).decode('UTF-8')
            self.connect(endpoint)
        elif command == "START":
            self.start()
            #self.run()
        elif command == "STOP":
            self.stop()
            try:
                self._pipe.send_unicode("OK", zmq.DONTWAIT)
            except zmq.error.Again:
                # other end of the pipe is already gone
                pass
            self._terminated = True

        elif command == "WHISPER":
            # Get peer to send message to
            peer_id = uuid.UUID(bytes=request.pop(0))
            # Send frame on out to peer's mailbox, drop message
            # if peer doesn't exist (may have been destroyed)
            if self.peers.get(peer_id):
                msg = ZreMsg(ZreMsg.WHISPER)
                msg.set_address(peer)
                msg.content = request
                self.peers[peer].send(msg)
        elif command == "SHOUT":
            # Get group to send message to
            grpname = request.pop(0).decode('UTF-8')
            msg = ZreMsg(ZreMsg.SHOUT)
            msg.set_group(grpname)
            msg.content = request.pop(0)

            if self.peer_groups.get(grpname):
                self.peer_groups[grpname].send(msg)

            else:
                logger.warning("Group {0} not found.".format(grpname))

        elif command == "JOIN":
            grpname = request.pop(0).decode('UTF-8')
            grp = self.own_groups.get(grpname)
            if not grp:
                # Only send if we're not already in group
                grp = PyreGroup(grpname)
                self.own_groups[grpname] = grp
                msg = ZreMsg(ZreMsg.JOIN)
                msg.set_group(grpname)
                self.status += 1
                msg.set_status(self.status)

                for peer in self.peers.values():
                    peer.send(msg)

                logger.debug("Node is joining group {0}".format(grpname))

        elif command == "LEAVE":
            grpname = request.pop(0).decode('UTF-8')
            grp = self.own_groups.get(grpname)
            if grp:
                # Only send if we're actually in group
                msg = ZreMsg(ZreMsg.LEAVE)
                msg.set_group(grpname)
                self.status += 1
                msg.set_status(self.status)

                for peer in self.peers.values():
                    peer.send(msg)

                self.own_groups.pop(grpname)

                logger.debug("Node is leaving group {0}".format(grpname))
        elif command == "$TERM":
            pass

        elif command == "STOP":
            self.stop()
            try:
                self._pipe.send_unicode("OK", zmq.DONTWAIT)
            except zmq.error.Again:
                # other end of the pipe is already gone
                pass
            self._terminated = True

        else:
            logger.warning("Unkown Node API command: {0}".format(command))

    # Here we handle messages coming from other peers
    def recv_peer(self):
        zmsg = ZreMsg()
        zmsg.recv(self.inbox)
        #msgs = self.inbox.recv_multipart()
        # Router socket tells us the identity of this peer
        id = zmsg.get_address()
        # On HELLO we may create the peer if it's unknown
        # On other commands the peer must already exist
        peer = self.peers.get(id)
        #print(p, id)
        if zmsg.id == ZreMsg.HELLO:
            if (peer):
                # remove fake peers
                if peer.get_ready():
                    self.remove_peer(peer)
                elif peer.endpoint == self.endpoint:
                    # We ignore HELLO, if peer has same endpoint as current node
                    return

            peer = self.require_peer(id, zmsg.get_endpoint())
            peer.set_ready(True)

        # Ignore command if peer isn't ready
        if not peer or not peer.get_ready():
            logger.warning("Peer {0} isn't ready".format(peer))
            return

        if not peer.check_message(zmsg):
            logger.warning("{0} lost messages from {1}".format(self.identity, peer.identity))

        if zmsg.id == ZreMsg.HELLO:
            # Join peer to listed groups
            peer.set_name(zmsg.get_name())
            peer.set_status(zmsg.get_status())
            peer.set_headers(zmsg.get_headers())

            # Now tell the caller about the peer
            self._pipe.send_unicode("ENTER", flags=zmq.SNDMORE)
            self._pipe.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
            self._pipe.send_unicode(peer.get_name(), flags=zmq.SNDMORE)
            # TODO send headers???
            self._pipe.send_unicode(peer.get_endpoint())

            # Join peer to listed groups
            for grp in zmsg.get_groups():
                self.join_peer_group(peer, grp)
        elif zmsg.id == ZreMsg.WHISPER:
            # Pass up to caller API as WHISPER event
            self._pipe.send_unicode("WHISPER", zmq.SNDMORE)
            self._pipe.send(peer.get_identity().bytes, zmq.SNDMORE)
            self._pipe.send_unicode(peer.get_name(), zmq.SNDMORE)
            self._pipe.send(zmsg.content)
        elif zmsg.id == ZreMsg.SHOUT:
            # Pass up to caller API as WHISPER event
            self._pipe.send_unicode("SHOUT", zmq.SNDMORE)
            self._pipe.send(peer.get_identity().bytes, zmq.SNDMORE)
            self._pipe.send_unicode(peer.get_name(), zmq.SNDMORE)
            self._pipe.send_unicode(zmsg.get_group(), zmq.SNDMORE)
            self._pipe.send(zmsg.content)
        elif zmsg.id == ZreMsg.PING:
            peer.send(ZreMsg(id=ZreMsg.PING_OK))
        elif zmsg.id == ZreMsg.JOIN:
            self.join_peer_group(peer, zmsg.get_group())
            #assert (zre_msg_status (msg) == zre_peer_status (peer))
        elif zmsg.id == ZreMsg.LEAVE:
            self.leave_peer_group(zmsg.get_group())
            peer.refresh()
            self.leave_peer_group(p, zmsg.get_group())
        peer.refresh()

    def recv_beacon(self):
        msgs = self.beacon.get_socket().recv_multipart()
        ipaddress = msgs.pop(0)
        frame = msgs.pop(0)
        beacon = struct.unpack('cccb16sH', frame)
        # Ignore anything that isn't a valid beacon

        if beacon[3] != BEACON_VERSION:
            logger.warning("Invalid ZRE Beacon version: {0}".format(beacon[3]))
            return

        peer_id = uuid.UUID(bytes=beacon[4])
        #print("peerId: %s", peer_id)
        port = socket.ntohs(beacon[5])
        # if we receive a beacon with port 0 this means the peer exited
        if port:
            endpoint = "tcp://%s:%d" %(ipaddress.decode('UTF-8'), port)
            peer = self.require_peer(peer_id, endpoint)
            peer.refresh()
        else:
            # Zero port means peer is going away; remove it if
            # we had any knowledge of it already
            peer = self.peers.get(peer_id)
            # remove the peer (delete)
            if peer:
                self.remove_peer(peer)

            else:
                logger.warning("We don't know peer id {0}".format(peer_id))

    #  Remove peer from group, if it's a member
    def delete_peer(self, peer, group):
        group.leave(peer)

    def ping_peer(self, peer_id):
        peer = self.peers.get(peer_id)
        if time.time() > peer.expired_at:
            self.remove_peer(peer)
        elif time.time() > peer.evasive_at:
            # If peer is being evasive, force a TCP ping.
            # TODO: do this only once for a peer in this state;
            # it would be nicer to use a proper state machine
            # for peer management.
            msg = ZreMsg(ZreMsg.PING)
            peer.send(msg)

    def run(self):
        # TODO: Signal actor successfully initialized
        reap_at = time.time() + REAP_INTERVAL
        while(True):
            timeout = reap_at - time.time()
            if timeout < 0:
                timeout = 0

            items = dict(self.poller.poll(timeout * 1000))

            if self._pipe in items and items[self._pipe] == zmq.POLLIN:
                self.recv_api()
            if self.inbox in items and items[self.inbox] == zmq.POLLIN:
                self.recv_peer()
            if self.beacon.get_socket() in items and items[self.beacon.get_socket()] == zmq.POLLIN:
                self.recv_beacon()
            if time.time() >= reap_at:
                reap_at = time.time() + REAP_INTERVAL
                # Ping all peers and reap any expired ones
                for peer_id in self.peers.copy().keys():
                    self.ping_peer(peer_id)


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
