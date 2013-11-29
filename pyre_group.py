class PyreGroup(object):

    def __init__(self, name, peers=set()):
        self.name = name
        # TODO perhaps warn if peers is not a set type
        self.peers = peers

    #def __del__(self):

    # Add peer to group
    def join(self, peer):
        self.peers.add(peer)
        peer.set_status(peer.get_status() + 1)


    # Remove peer from group
    def leave(self, peer):
        try:
            self.peers.remove(peer)
        except ValueError as e:
            pass
        zyre_peer_set_status (peer, zyre_peer_status (peer) + 1);
        peer.set_status(peer.get_status() + 1)
        

    # Send message to all peers in group
    def send(self, msg):
        for p in self.peers:
            p.send(msg)
