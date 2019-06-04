import time
import zmq
import logging

logger = logging.getLogger(__name__)


class PyrePeer(object):

    PEER_EXPIRED = 30              # expire after 10s
    PEER_EVASIVE = 10              # mark evasive after 5s

    def __init__(self, ctx, identity):
        # TODO: what to do with container?
        self._ctx = ctx          # ZMQ context
        self.mailbox = None      # Socket through to peer
        self.identity = identity # Identity UUID
        self.endpoint = None     # Endpoint connected to
        self.name = "notset"     # Peer's public name
        self.origin = "unknown"  # Origin node's public name
        self.evasive_at = 0      # Peer is being evasive
        self.expired_at = 0      # Peer has expired by now
        self.connected = False   # Peer will send messages
        self.ready = False       # Peer has said Hello to us
        self.status = 0          # Our status counter
        self.sent_sequence = 0   # Outgoing message sequence
        self.want_sequence = 0   # Incoming message sequence
        self.headers = {}        # Peer headers

    def __del__(self):
        self.disconnect()

    # Connect peer mailbox
    def connect(self, reply_to, endpoint):
        if self.connected:
            return

        # Create new outgoing socket (drop any messages in transit)
        self.mailbox = zmq.Socket(self._ctx, zmq.DEALER)
        # Set our caller 'From' identity so that receiving node knows
        # who each message came from.
        # Set our own identity on the socket so that receiving node
        # knows who each message came from. Note that we cannot use
        # the UUID directly as the identity since it may contain a
        # zero byte at the start, which libzmq does not like for
        # historical and arguably bogus reasons that it nonetheless
        # enforces.
        # we set linger to 0 by default (In zyre this is done by czmq's zsys)
        self.mailbox.setsockopt(zmq.LINGER, 0)
        self.mailbox.setsockopt(zmq.IDENTITY, b'\x01' + reply_to.bytes)
        # Set a high-water mark that allows for reasonable activity
        self.mailbox.setsockopt(zmq.SNDHWM, PyrePeer.PEER_EXPIRED * 100)
        # Send messages immediately or return EAGAIN
        self.mailbox.setsockopt(zmq.SNDTIMEO, 0)

        # Connect through to peer node
        logger.debug("Connecting to peer {0} on endpoint {1}".format(self.identity, endpoint))

        self.mailbox.connect(endpoint)
        self.endpoint = endpoint
        self.connected = True
        self.ready = False

    # Disconnect peer mailbox
    # No more messages will be sent to peer until connected again
    def disconnect(self):
        # If connected, destroy socket and drop all pending messages
        if (self.connected):
            logger.debug("{0} Disconnecting peer {1}".format(self.origin, self.name))
            self.mailbox.close()
            self.mailbox = None
            self.endpoint = ""
            self.connected = False
            self.ready = False
    # end disconnect

    # Send message to peer
    def send(self, msg):
        if self.connected:
            self.sent_sequence += 1
            self.sent_sequence = self.sent_sequence % 65535
            msg.set_sequence(self.sent_sequence)

            try:
                msg.send(self.mailbox)
            except zmq.Again as e:
                self.disconnect()
                logger.debug("{0} Error while sending {1} to peer={2} sequence={3}".format(self.origin,
                                                                            msg.get_command(),
                                                                            self.name,
                                                                            msg.get_sequence()))
                return -1

            logger.debug("{0} send {1} to peer={2} sequence={3}".format(self.origin,
                msg.get_command(),
                self.name,
                msg.get_sequence()))

        else:
            logger.debug("Peer {0} is not connected".format(self.identity))
    # end send

    # Return peer connected status
    def is_connected(self):
        return self.connected
    # end is_connected

    # Return peer identity string
    def get_identity(self):
        return self.identity
    # end get_identity

    # Return peer connection endpoint
    def get_endpoint(self):
        if self.connected:
            return self.endpoint
        else:
            return ""
    # end get_endpoint

    # Register activity at peer
    def refresh(self):
        self.evasive_at = time.time() + self.PEER_EVASIVE
        self.expired_at = time.time() + self.PEER_EXPIRED
    # end refresh

    # Return future evasive time
    def evasive_at(self):
        return self.evasive_at
    # end evasiv_at

    # Return future expired time
    def expired_at(self):
        return self.expired_at
    # end expired_at

    # Return peer name
    def get_name(self):
        return self.name

    # Set peer name
    def set_name(self, name):
        self.name = name

    # Set current node name, for logging
    def set_origin(self, origin):
        self.origin = origin

    # Return peer status
    def get_status(self):
        return self.status
    # end get_status

    # Set peer status
    def set_status(self, status):
        self.status = status & 0xFF
    # end set_status

    # Return peer ready state
    def get_ready(self):
        return self.ready
    # end get_ready

    # Set peer ready state
    def set_ready(self, ready):
        self.ready = ready
    # end set_ready

    # Get peer header value
    def get_header(self, key):
        return self.headers.get(key, "")
    # end get_header

    # Get peer headers
    def get_headers(self):
        return self.headers

    # Set peer headers
    def set_headers(self, headers):
        self.headers = headers
    # end set_headers

    # Check if messages were lost from peer, returns true if they were
    def messages_lost(self, msg):
        # The sequence number set by the peer, and our own calculated
        # sequence number should be the same.
        logger.debug("(%s) recv %s from peer=%s sequence=%d"%(
            self.origin,
            msg.get_command(),
            self.name,
            msg.get_sequence()) )
        if msg.get_command == "HELLO":
            self.want_sequence = 1
        else:
            self.want_sequence += 1
            self.want_sequence = self.want_sequence % 65535

        if self.want_sequence != msg.get_sequence():
            logger.debug("(%s) seq error from peer=%s expect=%d, got=%d",
                self.origin,
                self.name,
                self.want_sequence,
                msg.get_sequence())
            return True;
        return False
    # end check_message
