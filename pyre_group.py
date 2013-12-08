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
        try:
            self.peers.pop(peer.get_identity())
        except KeyError as e:
            print("Removing peer %s from %s failed, probably it isn't there?" %(peer, self.peers))
        peer.set_status(peer.get_status() + 1)

    # Send message to all peers in group
    def send(self, msg):
        for p in self.peers.values():
            p.send(msg)
