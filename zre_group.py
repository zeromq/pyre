class ZreGroup(object):

    def __init__(self, name, peers=[]):
        self.name = name
        self.peers = peers

    #def __del__(self):

    # Add peer to group
    def join(self, peer):
        self.peers.append(peer)

    # Remove peer from group
    def leave(self, peer):
        self.peers.remove(peer)

    # Send message to all peers in group
    def send(self, msg):
        for p in self.peers:
            p.send(msg)
