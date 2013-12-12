import zmq
import time
import binascii
import os
import struct
import socket
import uuid
# local modules
from . import zbeacon
from . import zhelper
from .zre_msg import ZreMsg
from .pyre_peer import PyrePeer
from .pyre_group import PyreGroup

BEACON_VERSION = 1
ZRE_DISCOVERY_PORT = 5670
REAP_INTERVAL = 1.0  # Once per second

class Pyre(object):

    def __init__(self, ctx=zmq.Context()):
        self._ctx = ctx
        self.verbose = False
        self._pipe = zhelper.zthread_fork(self._ctx, PyreNode)

    def stop(self):
        self._pipe.send_unicode("STOP")

    # Receive next message from node
    def recv(self):
        return self._pipe.recv()

    # Set node tracing on or off
    def set_verbose(self, verbose=True):
        self.verbose = verbose

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

    # Return node socket, for polling
    def get_socket(self):
        return self._pipe

    # Set node header value
    def set_header(self, name, format, *args):
        self._pipe.send_unicode("SET", flags=zmq.SNDMORE)
        self._pipe.send_unicode( name, flags=zmq.SNDMORE)
        self._pipe.send_unicode(value, flags=zmq.SNDMORE)

class PyreNode(object):

    def __init__(self, ctx, pipe):
        self._ctx = ctx
        self._pipe = pipe
        self._terminated = False
        self.inbox = ctx.socket(zmq.ROUTER)
        self.port = self.inbox.bind_to_random_port("tcp://*")
        self.status = 0
        if self.port < 0:
            print("ERROR setting up agent port")
        self.poller = zmq.Poller()
        self.identity = uuid.uuid4()
        print("myID: %s"% self.identity)
        self.beacon = zbeacon.ZBeacon(self._ctx, ZRE_DISCOVERY_PORT)
        # TODO: how do we set the header of the beacon?
        # line 299 zbeacon.c
        self.beacon.set_noecho()
        # construct a header
        transmit = struct.pack('cccb16sH', b'Z',b'R',b'E', 
                               BEACON_VERSION, self.identity.bytes, 
                               socket.htons(self.port))
        self.beacon.publish(transmit)
        # construct the header filter 
        # (to discard none zre messages)
        filter = struct.pack("ccc", b'Z',b'R',b'E')
        self.beacon.subscribe(filter)

        self.host = self.beacon.get_hostname()
        self.peers = {}
        self.peer_groups = {}
        self.own_groups = {}
        # TODO what is this used for?
        self.headers = {}
        self.run()

    # def __del__(self):
        # destroy beacon

    def stop(self):
        stop_transmit = struct.pack('cccb16sH', b'Z',b'R',b'E', 
                               BEACON_VERSION, self.identity.bytes, 
                               socket.htons(0))
        self.beacon.publish(stop_transmit)
        # Give time for beacon to go out
        time.sleep(0.001)

    # Send message to all peers
    def send_peer(self, peer, msg):
        peer.send(msg)

    def purge_peer(self, peer, endpoint):
        if (peer.get_endpoint() == endpoint):
            peer.disconnect()

    def remove_peer(self, peer):
        self._pipe.send_unicode("EXIT", flags=zmq.SNDMORE)
        self._pipe.send(peer.get_identity().bytes)
        # If peer has really vanished, expire it (delete)
        for grp in self.peer_groups.values():
            self.delete_peer(peer, grp)
        self.peers.pop(peer.get_identity())

    # Find or create peer via its UUID string
    def require_peer(self, identity, ipaddr, port):
        #  Purge any previous peer on same endpoint
        p = self.peers.get(identity)
        if not p:
            # Purge any previous peer on same endpoint
            endpoint = "%s:%u" %(ipaddr, port)
            for peer_id, peer in self.peers.copy().items():
                self.purge_peer(peer, endpoint)

            p = PyrePeer(self._ctx, identity)
            self.peers[identity] = p
            #print("Require_peer: %s" %identity)
            p.connect(self.identity, "%s:%u" %(ipaddr, port))
            m = ZreMsg(ZreMsg.HELLO)
            m.set_ipaddress(self.host)
            m.set_mailbox(self.port)
            m.set_groups(self.own_groups.keys())
            m.set_status(self.status)
            p.send(m)

            # Now tell the caller about the peer
            self._pipe.send_unicode("ENTER", flags=zmq.SNDMORE);
            self._pipe.send(identity.bytes)
        return p

    # Find or create group via its name
    def require_peer_group(self, groupname):
        grp = self.peer_groups.get(groupname)
        if not grp:
            grp = PyreGroup(groupname)
            self.peer_groups[groupname] = grp 
        return grp

    def join_peer_group(self, peer, name):
        grp = self.require_peer_group(name)
        grp.join(peer)
        # Now tell the caller about the peer joined group
        self._pipe.send_unicode("JOIN", flags=zmq.SNDMORE)
        self._pipe.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
        self._pipe.send_unicode(name)
        return grp

    # Here we handle the different control messages from the front-end
    def recv_api(self):
        cmds = self._pipe.recv_multipart()
        command = cmds.pop(0).decode('UTF-8')
        if command == "WHISPER":
            # Get peer to send message to
            peer = uuid.UUID(bytes=cmds.pop(0))
            # Send frame on out to peer's mailbox, drop message
            # if peer doesn't exist (may have been destroyed)
            if self.peers.get(peer):
                msg = ZreMsg(ZreMsg.WHISPER)
                msg.set_address(peer)
                msg.content = cmds
                self.peers[peer].send(msg)
        elif command == "SHOUT":
            # Get group to send message to
            grpname = cmds.pop(0).decode('UTF-8')
            msg = ZreMsg(ZreMsg.SHOUT)
            msg.set_group(grpname)
            msg.content = cmds.pop(0)
            if self.peer_groups.get(grpname):
                self.peer_groups[grpname].send(msg)
            else:
                print("group %s not found" %grpname)
                #print(self.peer_groups)
        elif command == "JOIN":
            grpname = cmds.pop(0).decode('UTF-8')
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
                print("Node is joining group %s" % grpname)
        elif command == "LEAVE":
            grpname = cmds.pop(0).decode('UTF-8')
            grp = self.own_groups.get(grpname)
            if grp:
                # Only send if we're actually in group
                msg = ZreMsg(ZreMsg.LEAVE)
                msg.set_group(grpname)
                self.status += 1
                msg.set_status(self.status)
                for peer in self.peers:
                    peer.send(msg)
                self.own_groups.pop(grpname)
                print("Node is leaving group %s" % grpname)
        elif command == "STOP":
            self.stop()
            self._pipe.send_unicode("OK")
            self._terminated = True
        else:
            print('Unkown Node API command: %s' %command)

    # Here we handle messages coming from other peers
    def recv_peer(self):
        zmsg = ZreMsg()
        zmsg.recv(self.inbox)
        #msgs = self.inbox.recv_multipart()
        # Router socket tells us the identity of this peer
        id = zmsg.get_address()
        # On HELLO we may create the peer if it's unknown
        # On other commands the peer must already exist
        p = self.peers.get(id)
        #print(p, id)
        if zmsg.id == ZreMsg.HELLO:
            p = self.require_peer(id, zmsg.get_ipaddress(), zmsg.get_mailbox())
            p.set_ready(True)
            #print("Hallo %s"%p)

        # Ignore command if peer isn't ready
        if not p or not p.get_ready():
            print("Peer %s isn't ready" %p)
            return
        if not p.check_message(zmsg):
            print("W: [%s] lost messages from %s" %(self.identity, p.identity))
        if zmsg.id == ZreMsg.HELLO:
            # Join peer to listed groups
            for grp in zmsg.get_groups():
                self.join_peer_group(p, grp)
            # Hello command holds latest status of peer
            p.set_status(zmsg.get_status())
            # Store peer headers for future reference
            p.set_headers(zmsg.get_headers())
        elif zmsg.id == ZreMsg.WHISPER:
            # Pass up to caller API as WHISPER event
            self._pipe.send_unicode("WHISPER", zmq.SNDMORE)
            self._pipe.send(p.get_identity().bytes, zmq.SNDMORE)
            self._pipe.send(zmsg.content)
        elif zmsg.id == ZreMsg.SHOUT:
            # Pass up to caller API as WHISPER event
            self._pipe.send_unicode("SHOUT", zmq.SNDMORE)
            self._pipe.send(p.get_identity().bytes, zmq.SNDMORE)
            self._pipe.send_unicode(zmsg.get_group(), zmq.SNDMORE)
            self._pipe.send(zmsg.content)
        elif zmsg.id == ZreMsg.PING:
            p.send(ZreMsg(id=ZreMsg.PING_OK))
        elif zmsg.id == ZreMsg.JOIN:
            self.join_peer_group(p, zmsg.get_group())
            #assert (zre_msg_status (msg) == zre_peer_status (peer))
        elif zmsg.id == ZreMsg.LEAVE:
            self.leave_peer_group(zmsg.get_group())
        p.refresh()

    def recv_beacon(self):
        msgs = self.beacon.get_socket().recv_multipart()
        ipaddress = msgs.pop(0)
        frame = msgs.pop(0)
        beacon = struct.unpack('cccb16sH', frame)
        # Ignore anything that isn't a valid beacon
        if beacon[3] != BEACON_VERSION:
            print("Invalid ZRE Beacon version: %s" %beacon[3])
            return
        peer_id = uuid.UUID(bytes=beacon[4])
        #print("peerId: %s", peer_id)
        port = socket.ntohs(beacon[5])
        peer = self.require_peer(peer_id, ipaddress.decode('UTF-8'), port)
        # if we receive a beacon with port 0 this means the peer exited
        if port == 0:
            # remove the peer (delete)
            self.remove_peer(peer)
        else:
            peer.refresh()

    #  Remove peer from group, if it's a member
    def delete_peer(self, peer, group):
        group.leave(peer)

    def ping_peer(self, peer_id):
        p = self.peers.get(peer_id)
        if time.time() > p.expired_at:
            self.remove_peer(p)
        elif time.time() > p.evasive_at:
            # If peer is being evasive, force a TCP ping.
            # TODO: do this only once for a peer in this state;
            # it would be nicer to use a proper state machine
            # for peer management.
            msg = ZreMsg(ZreMsg.PING)
            p.send(msg)

    def run(self):
        self.poller.register(self._pipe, zmq.POLLIN)
        self.poller.register(self.inbox, zmq.POLLIN)
        self.poller.register(self.beacon.get_socket(), zmq.POLLIN)

        reap_at = time.time() + REAP_INTERVAL
        while(True):
            timeout = reap_at - time.time();
            if timeout < 0:
                timeout = 0

            items = dict(self.poller.poll(timeout*1000))

            if self._pipe in items and items[self._pipe] == zmq.POLLIN:
                self.recv_api()
                #print("PIPED:")
            if self.inbox in items and items[self.inbox] == zmq.POLLIN:
                self.recv_peer()
                #print("NODE?:")
            if self.beacon.get_socket() in items and items[self.beacon.get_socket()] == zmq.POLLIN:
                self.recv_beacon()
            if time.time() >= reap_at:
                reap_at = time.time() + REAP_INTERVAL
                # Ping all peers and reap any expired ones
                for peer_id in self.peers.copy().keys():
                    self.ping_peer(peer_id)
            if self._terminated:
                break

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
            print("CHAT_TASK: %s" % message)
            n.shout("CHAT", message)
        if n.get_socket() in items and items[n.get_socket()] == zmq.POLLIN:
            cmds = n.get_socket().recv_multipart()
            type = cmds.pop(0)
            print("NODE_MSG TYPE: %s" % type)
            print("NODE_MSG PEER: %s" % uuid.UUID(bytes=cmds.pop(0)))
            if type.decode('utf-8') == "SHOUT":
                print("NODE_MSG GROUP: %s" % cmds.pop(0))
            print("NODE_MSG CONT: %s" % cmds)


if __name__ == '__main__':
    ctx = zmq.Context()
    chat_pipe = zhelper.zthread_fork(ctx, chat_task)
    while True:
        try:
            msg = input()
            chat_pipe.send(msg.encode('utf_8'))
        except (KeyboardInterrupt, SystemExit):
            break
    print("FINISHED")
