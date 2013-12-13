Pyre
====

This is a Python port of [Zyre](zyre.org), implementing the same [ZRE protocol](http://rfc.zeromq.org/spec:20).

# Pyre - an open-source framework for proximity-based peer-to-peer applications

## Description

Pyre does local area discovery and clustering. A Pyre node broadcasts
UDP beacons, and connects to peers that it finds. This class wraps a
Pyre node with a message-based API.

All incoming events are messages delivered via the recv call of a Pyre
instance. The first frame defines the type of the message, and following
frames provide further values:

    ENTER fromnode headers
        a new peer has entered the network
    EXIT fromnode
        a peer has left the network
    JOIN fromnode groupname
        a peer has joined a specific group
    LEAVE fromnode groupname
        a peer has joined a specific group
    WHISPER fromnode message
        a peer has sent this node a message
    SHOUT fromnode groupname message
        a peer has sent one of our groups a message

In SHOUT and WHISPER the message is a single frame in this version
of Zyre. In ENTER, the headers frame contains a packed dictionary,
see zhash_pack/unpack.

To join or leave a group, use the join() and leave() methods.
To set a header value, use the set_header() method. To send a message
to a single peer, use whisper(). To send a message to a group, use
shout().

## API

    import pyre
    #  Constructor, creates a new Zyre node. Note that until you start the
    #  node it is silent and invisible to other nodes on the network.
    node = pyre.Pyre()

    #  Set node header; these are provided to other nodes during discovery
    #  and come in each ENTER message.
    node.set_header(name, value)

    #  (TODO: Currently a Pyre node starts immediately) Start node, after setting header values. When you start a node it
    #  begins discovery and connection.
    node.start()

    #  Stop node, this signals to other peers that this node will go away.
    #  This is polite; however you can also just destroy the node without
    #  stopping it.
    node.stop()

    #  Join a named group; after joining a group you can send messages to
    #  the group and all Zyre nodes in that group will receive them.
    node.join(group)

    #  Leave a group
    node.leave(group)

    #  Receive next message from network; the message may be a control
    #  message (ENTER, EXIT, JOIN, LEAVE) or data (WHISPER, SHOUT).
    #  Returns a list of message frames
    msgs = node.recv();

    # Send message to single peer, specified as a UUID object (import uuid)
    # Destroys message after sending
    node.whisper(peer, msg)

    # Send message to a named group
    # Destroys message after sending
    node.shout(group, msg);

    #  Send string to single peer specified as a UUID string.
    #  String is formatted using printf specifiers.
    node.whispers(peer, msg_string)

    #  Send message to a named group
    #  Destroys message after sending
    node.shouts(group, msg_string);
        
    #  Return handle to the Zyre node, for polling
    node.get_socket()


## Example

    import sys
    import time
    import uuid
    import zmq
    from pyre import Pyre
    from pyre import zhelper

    def chat_task(ctx, pipe):
        node = Pyre(ctx)
        node.join("CHAT")

        poller = zmq.Poller()
        poller.register(pipe, zmq.POLLIN)
        poller.register(node.get_socket(), zmq.POLLIN)
        while(True):
            try:
                items = dict(poller.poll())
                if pipe in items and items[pipe] == zmq.POLLIN:
                    message = pipe.recv()
                    if message.decode('utf-8') == "quit":
                        break
                    print("CHAT_TASK: %s" % message)
                    n.shout("CHAT", message)
                if n.get_socket() in items and items[n.get_socket()] == zmq.POLLIN:
                    cmds = n.get_socket().recv_multipart()
                    type = cmds.pop(0)
                    print("-------------------------------------")
                    print("NODE_MSG TYPE: %s" % type)
                    print("NODE_MSG PEER: %s" % uuid.UUID(bytes=cmds.pop(0)))
                    if type.decode('utf-8') == "SHOUT":
                        print("NODE_MSG GROUP: %s" % cmds.pop(0))
                        print("CHAT: %s" %cmds[0].decode('utf-8'))
                    else:
                        print("NODE_MSG CONT: %s" % cmds)
            except (KeyboardInterrupt, SystemExit):
                break
        node.stop()

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


## Project Organization

Pyre is owned by all its authors and contributors. This is an open source
project licensed under the LGPLv3. To contribute to Zyre please read the
[C4.1 process](http://rfc.zeromq.org/spec:22) that we use.

To report an issue, use the [PYRE issue tracker](https://github.com/zeromq/pyre/issues) at github.com.