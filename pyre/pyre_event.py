import zmq, uuid, json

class PyreEvent(object):
    """Parsing Pyre messages

    This class provides a higher-level API to the Pyre.recv() call, by doing
    work that you will want to do in many cases, such as unpacking the peer
    headers for each ENTER event received.
    """
    def __init__(self, node):
        """Constructor, creates a new Pyre event. Receive an event from the Pyre node, wraps Pyre.recv.

        Args:
            node (Pyre): Pyre node
        """
        super(PyreEvent, self).__init__()
        incoming = node.recv()

        self.type = incoming.pop(0).decode('utf-8')
        self.peer_uuid_bytes = incoming.pop(0)
        self.peer_name = incoming.pop(0).decode('utf-8')
        self.headers = None
        self.peer_addr = None
        self.group = None
        self.msg = None
        if self.type == "ENTER":
            self.headers = json.loads(incoming.pop(0).decode('utf-8'))
            self.peer_addr = incoming.pop(0).decode('utf-8')
        elif self.type == "JOIN" or self.type == "LEAVE":
            self.group = incoming.pop(0).decode('utf-8')
        elif self.type == "WHISPER":
            self.msg = incoming
        elif self.type == "SHOUT":
            self.group = incoming.pop(0).decode('utf-8')
            self.msg = incoming

    def header(self,name):
        """Getter for single header values

        Args:
            name (str): Header name

        Returns:
            str: Header value
        """
        if self.headers and name in self.headers:
            return self.headers[name]
        return None

    @property
    def peer_uuid(self):
        """Creates uuid.UUID object

        Returns:
            TYPE: uuid.UUID
        """
        return uuid.UUID(bytes=self.peer_uuid_bytes)

    def __str__(self):
        return '<%s %s from %s>'%(__name__, self.type, self.peer_uuid.hex)