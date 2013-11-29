class PyreGroup(object):

    def __init__(self, name, peers=set()):
        self.name = name
        # TODO perhaps warn if peers is not a set type
        self.peers = peers

    #def __del__(self):

    # Add peer to group
    def join(self, peer):
        self.peers.add(peer.get_identity())
        peer.set_status(peer.get_status() + 1)


    # Remove peer from group
    def leave(self, peer):
        try:
            self.peers.remove(peer.get_identity())
        except KeyError as e:
            print("Remving peer %s from %s failed, probably it isn't there?" %(peer, self.peers))
        peer.set_status(peer.get_status() + 1)

    # Send message to all peers in group
    def send(self, msg):
        for p in self.peers:
            p.send(msg)
