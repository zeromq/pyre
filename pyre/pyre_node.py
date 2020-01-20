import zmq
import uuid
import logging
import struct
import socket
import time
import sys
from .zactor import ZActor
from .zbeacon import ZBeacon
from .zre_msg import ZreMsg
from .pyre_peer import PyrePeer
from .pyre_group import PyreGroup


BEACON_VERSION = 1
ZRE_DISCOVERY_PORT = 5670
REAP_INTERVAL = 1.0  # Once per second

logger = logging.getLogger(__name__)

class PyreNode(object):

    def __init__(self, ctx, pipe, outbox, *args, **kwargs):
        self._ctx = ctx                             #... until we use zbeacon actor
        self._pipe = pipe                           # We send command replies and signals to the pipe
                                                    # Pipe back to application
        self.outbox = outbox                        # Outbox back to application
        self._terminated = False                    # API shut us down
        self._verbose = False                       # Log all traffic (logging module?)
        self.beacon_port = ZRE_DISCOVERY_PORT       # Beacon port number
        self.interval = 0                           # Beacon interval 0=default
        self.beacon = None                          # Beacon actor
        self.beacon_socket = None                   # Beacon socket for polling
        self.poller = zmq.Poller()                  # Socket poller
        self.identity = uuid.uuid4()                # Our UUID as object
        self.bound = False
        self.inbox = ctx.socket(zmq.ROUTER)         # Our inbox socket (ROUTER)
        try:
            self.inbox.setsockopt(zmq.ROUTER_HANDOVER, 1)
        except AttributeError as e:
            logging.warning("can't set ROUTER_HANDOVER, needs zmq version >=4.1 but installed is {0}".format(zmq.zmq_version()))
        self.poller.register(self._pipe, zmq.POLLIN)
        self.name = str(self.identity)[:6]          # Our public name (default=first 6 uuid chars)
        self.endpoint = ""                          # Our public endpoint
        self.port = 0                               # Our inbox port, if any
        self.status = 0                             # Our own change counter
        self.peers = {}                             # Hash of known peers, fast lookup
        self.peer_groups = {}                       # Groups that our peers are in
        self.own_groups = {}                        # Groups that we are in
        self.headers = {}                           # Our header values
        # TODO: gossip stuff
        #self.start()
        self.run()

    # def __del__(self):
        # destroy beacon

    def start(self):
        # TODO: If application didn't bind explicitly, we grab an ephemeral port
        # on all available network interfaces. This is orthogonal to
        # beaconing, since we can connect to other peers and they will
        # gossip our endpoint to others.
        if self.beacon_port:
            # Start beacon discovery
            self.beacon = ZActor(self._ctx, ZBeacon)

            if self._verbose:
                self.beacon.send_unicode("VERBOSE")


            # Our hostname is provided by zbeacon
            self.beacon.send_unicode("CONFIGURE", zmq.SNDMORE)
            self.beacon.send(struct.pack("I", self.beacon_port))
            hostname = self.beacon.recv_unicode()

            #if self.interval:
            #   self.beacon.set_interval(self.interval)

            # Our hostname is provided by zbeacon
            self.port = self.inbox.bind_to_random_port("tcp://*")
            if self.port < 0:
                # Die on bad interface or port exhaustion
                logging.critical("Random port assignment for incoming messages failed. Exiting.")
                sys.exit(-1)
            else:
                self.bound = True
            self.endpoint = "tcp://%s:%d" %(hostname, self.port)

            # Set broadcast/listen beacon
            transmit = struct.pack('cccb16sH', b'Z', b'R', b'E',
                                   BEACON_VERSION, self.identity.bytes,
                                   socket.htons(self.port))
            self.beacon.send_unicode("PUBLISH", zmq.SNDMORE)
            self.beacon.send(transmit)
            # construct the header filter  (to discard none zre messages)
            filter = struct.pack("ccc", b'Z', b'R', b'E')
            self.beacon.send_unicode("SUBSCRIBE",zmq.SNDMORE)
            self.beacon.send(filter)

            self.beacon_socket = self.beacon.resolve()
            self.poller.register(self.beacon_socket, zmq.POLLIN)
        #else:
        # TODO: gossip stuff

        # Start polling on inbox
        self.poller.register(self.inbox, zmq.POLLIN)
        #logger.debug("Node identity: {0}".format(self.identity))

    def stop(self):
        logger.debug("Pyre node: stopping beacon")
        if self.beacon:
            if self.beacon.is_running:
                stop_transmit = struct.pack('cccb16sH', b'Z',b'R',b'E',
                                       BEACON_VERSION, self.identity.bytes,
                                       socket.htons(0))
                self.beacon.send_unicode("PUBLISH", zmq.SNDMORE)
                self.beacon.send(stop_transmit)
                # Give time for beacon to go out
                time.sleep(0.001)
            self.poller.unregister(self.beacon_socket)
            self.beacon.destroy()
            self.beacon = None
            self.beacon_socket = None

        self.beacon_port = 0

        if self.bound:
            # Stop polling on inbox
            self.poller.unregister(self.inbox)
        self.outbox.send_unicode("STOP", zmq.SNDMORE)
        self.outbox.send(self.identity.bytes, zmq.SNDMORE)
        self.outbox.send_unicode(self.name)

    def bind(self, endpoint):
        logger.warning("Not implemented")

    # Send message to all peers
    def send_peer(self, peer, msg):
        peer.send(msg)

    # TODO: log_item, dump

    # Here we handle the different control messages from the front-end
    def recv_api(self):
        request = self._pipe.recv_multipart()
        command = request.pop(0).decode('UTF-8')
        if command == "UUID":
            self._pipe.send(self.identity.bytes)
        elif command == "NAME":
            self._pipe.send_unicode(self.name)
        elif command == "SET NAME":
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
        #elif command == "SET ENDPOINT":
            # TODO: gossip start and endpoint setting
        # TODO: GOSSIP BIND, GOSSIP CONNECT
        #elif command == "BIND":
        #    # TODO: Needs a wait-signal
        #    endpoint = request.pop(0).decode('UTF-8')
        #    self.bind(endpoint)
        #elif command == "CONNECT":
        #    # TODO: Needs a wait-signal
        #    endpoint = request.pop(0).decode('UTF-8')
        #    self.connect(endpoint)
        elif command == "START":
            # zsock_signal (self->pipe, zyre_node_start (self));
            self.start()
            self._pipe.signal()
        elif command == "STOP":
            # zsock_signal (self->pipe, zyre_node_stop (self));
            self.stop()
            self._pipe.signal()
        elif command == "WHISPER":
            # Get peer to send message to
            peer_id = uuid.UUID(bytes=request.pop(0))
            # Send frame on out to peer's mailbox, drop message
            # if peer doesn't exist (may have been destroyed)
            if self.peers.get(peer_id):
                msg = ZreMsg(ZreMsg.WHISPER)
                msg.set_address(peer_id)
                msg.content = request
                self.peers[peer_id].send(msg)
        elif command == "SHOUT":
            # Get group to send message to
            grpname = request.pop(0).decode('UTF-8')
            msg = ZreMsg(ZreMsg.SHOUT)
            msg.set_group(grpname)
            msg.content = request  # request may contain multipart message

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
        elif command == "PEERS":
            self._pipe.send_pyobj(list(self.peers.keys()))
        elif command == "PEERS BY GROUP":
            grpname = request.pop(0).decode('UTF-8')
            grp = self.require_peer_group(grpname)
            self._pipe.send_pyobj(list(grp.peers.keys()))
        elif command == "ENDPOINT":
            self._pipe.send_unicode(self.endpoint)
        elif command == "PEER NAME":
            id = uuid.UUID(bytes=request.pop(0))
            peer = self.peers.get(id)
            if peer:
                self._pipe.send_unicode("%s" %peer.get_name())
            else:
                self._pipe.send_unicode("")
        elif command == "PEER ENDPOINT":
            id = uuid.UUID(bytes=request.pop(0))
            peer = self.peers.get(id)
            if peer:
                self._pipe.send_unicode("%s" %peer.get_endpoint())
            else:
                self._pipe.send_unicode("")
        elif command == "PEER HEADER":
            id = uuid.UUID(bytes=request.pop(0))
            key = request.pop(0).decode('UTF-8')
            peer = self.peers.get(id)
            if not peer:
                self._pipe.send_unicode("")
            else:
                self._pipe.send_unicode(peer.get_header(key))
        elif command == "PEER HEADERS":
            id = uuid.UUID(bytes=request.pop(0))
            peer = self.peers.get(id)
            if not peer:
                self._pipe.send_unicode("")
            else:
                self._pipe.send_pyobj(peer.get_headers())
        elif command == "PEER GROUPS":
            self._pipe.send_pyobj(list(self.peer_groups.keys()))
        elif command == "OWN GROUPS":
            self._pipe.send_pyobj(list(self.own_groups.keys()))
        elif command == "DUMP":
            # TODO: zyre_node_dump (self);
            pass
        elif command == "$TERM":
            # this is often not printed if program terminates
            logger.debug("Pyre node: shutting down")
            self._terminated = True

        else:
            logger.warning("Unkown Node API command: {0}".format(command))

    def purge_peer(self, peer, endpoint):
        if (peer.get_endpoint() == endpoint):
            self.remove_peer(peer)
            peer.disconnect()
            logger.debug("Purge peer: {0}{1}".format(peer,endpoint))

    # Find or create peer via its UUID string
    def require_peer(self, identity, endpoint):
        p = self.peers.get(identity)
        if not p:
            # Purge any previous peer on same endpoint
            for peer_id, peer in self.peers.copy().items():
                self.purge_peer(peer, endpoint)

            p = PyrePeer(self._ctx, identity)
            self.peers[identity] = p
            p.set_origin(self.name);
            # TODO: this could be handy, to set verbosity on a specific peer
            #zyre_peer_set_verbose (peer, self->verbose);
            p.connect(self.identity, endpoint)

            # Handshake discovery by sending HELLO as first message
            m = ZreMsg(ZreMsg.HELLO)
            m.set_endpoint(self.endpoint)
            m.set_groups(self.own_groups.keys())
            m.set_status(self.status)
            m.set_name(self.name)
            m.set_headers(self.headers)
            p.send(m)

        return p

    #  Remove peer from group, if it's a member
    def delete_peer(self, peer, group):
        group.leave(peer)

    #  Remove a peer from our data structures
    def remove_peer(self, peer):
        # Tell the calling application the peer has gone
        self.outbox.send_unicode("EXIT", zmq.SNDMORE)
        self.outbox.send(peer.get_identity().bytes, zmq.SNDMORE)
        self.outbox.send_unicode(peer.get_name())
        logger.debug("({0}) EXIT name={1}".format(peer, peer.get_endpoint()))
        # Remove peer from any groups we've got it in
        for grp in self.peer_groups.values():
            self.delete_peer(peer, grp)
        # To destroy peer, we remove from peers hash table (dict)
        self.peers.pop(peer.get_identity())

    # Find or create group via its name
    def require_peer_group(self, groupname):
        grp = self.peer_groups.get(groupname)
        if not grp:
            # somehow a dict containing peers is passed if
            # I don't force the peers arg to an empty dict
            grp = PyreGroup(groupname, peers={})
            self.peer_groups[groupname] = grp

        return grp

    def join_peer_group(self, peer, groupname):
        grp = self.require_peer_group(groupname)
        grp.join(peer)
        # Now tell the caller about the peer joined group
        self.outbox.send_unicode("JOIN", flags=zmq.SNDMORE)
        self.outbox.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
        self.outbox.send_unicode(peer.get_name(), flags=zmq.SNDMORE)
        self.outbox.send_unicode(groupname)
        logger.debug("({0}) JOIN name={1} group={2}".format(self.name, peer.get_name(), groupname))
        return grp

    def leave_peer_group(self, peer, groupname):
        # Tell the caller about the peer joined group
        self.outbox.send_unicode("LEAVE", flags=zmq.SNDMORE)
        self.outbox.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
        self.outbox.send_unicode(peer.get_name(), flags=zmq.SNDMORE)
        self.outbox.send_unicode(groupname)
        # Now remove the peer from the group
        grp = self.require_peer_group(groupname)
        grp.leave(peer)
        logger.debug("({0}) LEAVE name={1} group={2}".format(self.name, peer.get_name(), groupname))

    # Here we handle messages coming from other peers
    def recv_peer(self):
        zmsg = ZreMsg()
        zmsg.recv(self.inbox)
        #msgs = self.inbox.recv_multipart()
        # Router socket tells us the identity of this peer
        # First frame is sender identity
        id = zmsg.get_address()
        # On HELLO we may create the peer if it's unknown
        # On other commands the peer must already exist
        peer = self.peers.get(id)
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

        if peer.messages_lost(zmsg):
            logger.warning("{0} messages lost from {1}".format(self.identity, peer.identity))
            self.remove_peer(peer)
            return

        # Now process each command
        if zmsg.id == ZreMsg.HELLO:
            # Store properties from HELLO command into peer
            peer.set_name(zmsg.get_name())
            peer.set_headers(zmsg.get_headers())

            # Now tell the caller about the peer
            self.outbox.send_unicode("ENTER", flags=zmq.SNDMORE)
            self.outbox.send(peer.get_identity().bytes, flags=zmq.SNDMORE)
            self.outbox.send_unicode(peer.get_name(), flags=zmq.SNDMORE)
            self.outbox.send_json(peer.get_headers(),flags=zmq.SNDMORE)
            self.outbox.send_unicode(peer.get_endpoint())
            logger.debug("({0}) ENTER name={1} endpoint={2}".format(self.name, peer.get_name(), peer.get_endpoint()))

            # Join peer to listed groups
            for grp in zmsg.get_groups():
                self.join_peer_group(peer, grp)
            # Now take peer's status from HELLO, after joining groups
            peer.set_status(zmsg.get_status())
        elif zmsg.id == ZreMsg.WHISPER:
            # Pass up to caller API as WHISPER event
            self.outbox.send_unicode("WHISPER", zmq.SNDMORE)
            self.outbox.send(peer.get_identity().bytes, zmq.SNDMORE)
            self.outbox.send_unicode(peer.get_name(), zmq.SNDMORE)
            self.outbox.send_multipart(zmsg.content)
        elif zmsg.id == ZreMsg.SHOUT:
            # Pass up to caller API as WHISPER event
            self.outbox.send_unicode("SHOUT", zmq.SNDMORE)
            self.outbox.send(peer.get_identity().bytes, zmq.SNDMORE)
            self.outbox.send_unicode(peer.get_name(), zmq.SNDMORE)
            self.outbox.send_unicode(zmsg.get_group(), zmq.SNDMORE)
            self.outbox.send_multipart(zmsg.content)
        elif zmsg.id == ZreMsg.PING:
            peer.send(ZreMsg(id=ZreMsg.PING_OK))
        elif zmsg.id == ZreMsg.JOIN:
            self.join_peer_group(peer, zmsg.get_group())
            assert(zmsg.get_status() == peer.get_status())
        elif zmsg.id == ZreMsg.LEAVE:
            #self.leave_peer_group(zmsg.get_group())
            self.leave_peer_group(peer, zmsg.get_group())
            assert(zmsg.get_status() == peer.get_status())
        # Activity from peer resets peer timers
        peer.refresh()

    def recv_beacon(self):
        # Get IP address and beacon of peer
        try:
            ipaddress, frame = self.beacon_socket.recv_multipart()
        except ValueError:
            return

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
                logger.debug("Received 0 port beacon, removing peer {0}".format(peer))
                self.remove_peer(peer)

            else:
                logger.warning(self.peers)
                logger.warning("We don't know peer id {0}".format(peer_id))

    # TODO: Handle gossip dat

    # We do this once a second:
    # - if peer has gone quiet, send TCP ping
    # - if peer has disappeared, expire it
    def ping_peer(self, peer_id):
        peer = self.peers.get(peer_id)
        if time.time() > peer.expired_at:
            logger.debug("({0}) peer expired name={1} endpoint={2}".format(self.name, peer.get_name(), peer.get_endpoint()))
            self.remove_peer(peer)
        elif time.time() > peer.evasive_at:
            # If peer is being evasive, force a TCP ping.
            # TODO: do this only once for a peer in this state;
            # it would be nicer to use a proper state machine
            # for peer management.
            logger.debug("({0}) peer seems dead/slow name={1} endpoint={2}".format(self.name, peer.get_name(), peer.get_endpoint()))
            msg = ZreMsg(ZreMsg.PING)
            peer.send(msg)

    # --------------------------------------------------------------------------
    # This is the actor that runs a single node; it uses one thread, creates
    # a zyre_node object at start and destroys that when finishing.
    def run(self):

        # Signal actor successfully initialized
        self._pipe.signal()
        reap_at = time.time() + REAP_INTERVAL
        while not self._terminated:
            timeout = reap_at - time.time()
            if timeout < 0:
                timeout = 0
            items = dict(self.poller.poll(timeout * 1000))

            if self._pipe in items and items[self._pipe] == zmq.POLLIN:
                self.recv_api()
            if self.inbox in items and items[self.inbox] == zmq.POLLIN:
                self.recv_peer()
            if self.beacon_socket in items and items[self.beacon_socket] == zmq.POLLIN:
                self.recv_beacon()
            if time.time() >= reap_at:
                reap_at = time.time() + REAP_INTERVAL
                # Ping all peers and reap any expired ones
                for peer_id in self.peers.copy().keys():
                    self.ping_peer(peer_id)
