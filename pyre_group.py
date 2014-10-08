import logging

logger = logging.getLogger(__name__)


class PyreGroup(object):

    def __init__(self, name, peers=dict()):
        self.name = name
        # TODO perhaps warn if peers is not a set type
        self.peers = peers

    #def __del__(self):

    # Add peer to group
    def join(self, peer):
        self.peers[peer.get_identity()] = peer
        peer.set_status(peer.get_status() + 1)

    # Remove peer from group
    def leave(self, peer):
        peer_identity = peer.get_identity()
        if peer_identity in self.peers:
            self.peers.pop(peer.get_identity())

        else:
            logger.debug("Peer {0} is not in group {1}.".format(peer, self.name))

        peer.set_status(peer.get_status() + 1)

    # Send message to all peers in group
    def send(self, msg):
        for p in self.peers.values():
            p.send(msg)
