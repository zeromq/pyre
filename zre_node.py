import zmq
import time
import binascii
import os
import struct
import zhelper
import uuid
import zbeacon
from zre_msg import *
from zre_peer import *

BEACON_VERSION = 1
ZRE_DISCOVERY_PORT = 5120
REAP_INTERVAL = 1000  # Once per second

class ZreNode(object):

    def __init__(self, ctx):
        self._ctx = ctx
        self.verbose = False
        self._pipe = zhelper.zthread_fork(self._ctx, ZreNodeAgent)

    # def __del__(self):

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
    def whisper(self, msg):
        self._pipe.send_unicode("WHISPER", flags=zmq.SNDMORE)
        self._pipe.send_unicode(msg)

    # Send message to a group of peers
    def shout(self, msg):
        self._pipe.send_unicode("SHOUT", flags=zmq.SNDMORE)
        self._pipe.send_unicode(msg)

    # Return node handle, for polling
    # TOOO: rename this to socket because that's what it is
    def get_handle(self):
        return self._pipe

    # Set node header value
    def set_header(self, name, format, *args):
        self._pipe.send_unicode("SET", flags=zmq.SNDMORE)
        self._pipe.send_unicode( name, flags=zmq.SNDMORE)
        self._pipe.send_unicode(value, flags=zmq.SNDMORE)

class ZreNodeAgent(object):

    def __init__(self, ctx, pipe):
        self._ctx = ctx
        self._pipe = pipe
        self.inbox = ctx.socket(zmq.ROUTER)
        self.port = self.inbox.bind_to_random_port("tcp://*")
        print(self.port)
        if self.port < 0:
            print("ERROR setting up agent port")
        self.poller = zmq.Poller()
        self.identity = uuid.uuid4()
        print("myID", self.identity)
        self.beacon = zbeacon.ZBeacon(self._ctx, ZRE_DISCOVERY_PORT)
        # TODO: how do we set the header of the beacon?
        # line 299 zbeacon.c
        self.beacon.set_noecho()
        # construct a header
        transmit = struct.pack('cccb16sIb', b'Z',b'R',b'E', 
                               BEACON_VERSION, self.identity.bytes, 
                               self.port, 1)
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
    
    # Send message to all peers
    def peer_send(self, peer, msg):
        peer.send(msg)

    # Here we handle the different control messages from the front-end
    def recv_from_api(self):
        cmds = self._pipe.recv_multipart()
        command = cmds.pop().decode('UTF-8')
        if command == "WHISPER":
            # Get peer to send message to
            peer = cmds.pop().decode('UTF-8')
            # Send frame on out to peer's mailbox, drop message
            # if peer doesn't exist (may have been destroyed)
            if self.peers[peer]:
                self.peers[peer].send_multipart(cmds, copy=False)
        elif command == "SHOUT":
            # Get group to send message to
            group = cmds.pop().encode('UTF-8')
            if self.peer_groups[group]:
                self.peer_groups[group].send_multipart(cmds, copy=False)  
        else:
            print('Unkown Node API command: %s' %command)
            
    def peer_purge(self, peer):
        self.peers.pop(peer)

    # Find or create peer via its UUID string
    def require_peer(self, identity, address, port):
        #  Purge any previous peer on same endpoint
        # TODO match a uuid to a peer
        p = self.peers.get(identity)
        if not p:
            # TODO: Purge any previous peer on same endpoint
            p = ZrePeer(identity, address, port)
            self.peers[identity] = p
        p.connect(self.identity, "%s:%u" %(address, port))
        m = ZreMsg(ZreMsg.HELLO)
        m.set_ipaddress(self.host)
        m.set_mailbox(self.port)
        m.set_groups(self.own_groups.keys())
        msg.set_status(self.status)
        p.send(msg)

        # Now tell the caller about the peer
        self._pipe.send_unicode("ENTER", flags=zmq.SNDMORE);
        self._pipe.send(identity.bytes)
        return p

    # Find or create group via its name
    def require_peer_group(self, groupname):
        grp = self.peer_groups.get(groupname)
        if not grp:
            self.peer_groups[groupname] = group(groupname)
        return grp

    def join_peer_group(self, peer, name):
        grp = self.require_peer_group(name)
        grp.join(peer)
        # Now tell the caller about the peer joined group
        self._pipe.send_unicode("JOIN", flags=zmq.SNDMORE)
        self._pipe.send_unicode(peer.get_identity(), flags=zmq.SNDMORE)
        self._pipe.send_unicode(name)
        return grp

    # Here we handle messages coming from other peers
    def recv_from_peer(self):
        msgs = self.inbox.recv_multipart()
        print(msgs)
        # line 619
    def recv_beacon(self):
        msgs = self.beacon.get_socket().recv_multipart()
        ipaddress = msgs.pop(0)
        frame = msgs.pop(0)
        beacon = struct.unpack('cccb16sIb', frame)
        # Ignore anything that isn't a valid beacon
        if beacon[3] != BEACON_VERSION:
            print("Invalid ZRE Beacon version: %s" %beacon[3])
            return
        peer_id = uuid.UUID(bytes=beacon[4])
        print("peerId: %s", peer_id)
        port = beacon[5]
        peer = self.require_peer(peer_id, ipaddress, port)
        peer.refresh()

    #  Remove peer from group, if it's a member
    def peer_delete(self, peer, group):
        group.leave(peer)

    def peer_ping(self, peer):
        p = self.peers.get(peer)
        if time.time() > p.expiredAt:
            self._pipe.send_unicode("EXIT", flags=zmq.SNDMORE)
            self._pipe.send_unicode(p.get_identity())
            # TDOD DELETE FROM GROUPS
            self.get_purge(p)
        elif time.time() > p.evasive_at():
            # If peer is being evasive, force a TCP ping.
            # TODO: do this only once for a peer in this state;
            # it would be nicer to use a proper state machine
            # for peer management.
            msg = msg(msg.PING)
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

            items = dict(self.poller.poll(timeout))

            #print(items)
            if self._pipe in items and items[self._pipe] == zmq.POLLIN:
                self.recv_from_api()
                print("PIPED:")
            if self.inbox in items and items[self.inbox] == zmq.POLLIN:
                self.recv_from_peer()
                print("NODE?:")
            if self.beacon.get_socket() in items and items[self.beacon.get_socket()] == zmq.POLLIN:
                self.recv_beacon()

def chat_task(ctx, pipe):
    n = ZreNode(ctx)
    n.join("CHAT")

    poller = zmq.Poller()
    poller.register(pipe, zmq.POLLIN)
    poller.register(n.get_handle(), zmq.POLLIN)
    while(True):
        items = dict(poller.poll())
        print("basa", items)
        if pipe in items and items[pipe] == zmq.POLLIN:
            message = pipe.recv()
            print("CHAT_TASK: %s" % message)
        if n.get_handle() in items and items[n.get_handle()] == zmq.POLLIN:
            cmds = n.get_handle().recv_multipart()
            print("NODE_MSG: ", cmds)



if __name__ == '__main__':
    ctx = zmq.Context()
    chat_pipe = zhelper.zthread_fork(ctx, chat_task)
    while True:
        try:
            msg = chat_pipe.recv()
            print("CHATMSG: %s" %msg)
        except (KeyboardInterrupt, SystemExit):
            break
    print("FINISHED")
