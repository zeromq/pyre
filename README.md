Pyre
====

This is a Python port of [Zyre](zyre.org) 1.0, implementing the same [ZRE protocol](http://rfc.zeromq.org/spec:36).

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
of Pyre. In ENTER, the headers frame contains a packed dictionary, 
that can be unpacked using json.loads(msg) (see chat client).

To join or leave a group, use the join() and leave() methods.
To set a header value, use the set_header() method. To send a message
to a single peer, use whisper(). To send a message to a group, use
shout().

## Installation

For now use Pip:

    pip install https://github.com/zeromq/pyre/archive/master.zip

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
    # use node.get_socket().getsockopt(zmq.FD) to acquire 
    # the filedescriptor
    # Don't use this for getting Pyre events you can use the 
    # node.inbox to get those events

## Example Chat Client

```python
    from pyre import Pyre
    from pyre import zhelper
    import zmq
    import uuid
    import json


    def chat_task(ctx, pipe):
        n = Pyre("CHAT")
        n.set_header("CHAT_Header1","example header1")
	n.set_header("CHAT_Header2","example header2")
        n.join("CHAT")
        n.start()

        poller = zmq.Poller()
        poller.register(pipe, zmq.POLLIN)
        poller.register(n.inbox, zmq.POLLIN)

        while(True):
            items = dict(poller.poll())

            if pipe in items and items[pipe] == zmq.POLLIN:
                message = pipe.recv()

                # message to quit
                if message.decode('utf-8') == "$$STOP":
                    break

                print("CHAT_TASK: {0}".format(message))

                n.shout("CHAT", message)

            if n.inbox in items and items[n.inbox] == zmq.POLLIN:
                cmds = n.recv()
                msg_type = cmds.pop(0)

                peer_uuid_bytes = cmds.pop(0)
                peer_uuid = uuid.UUID(bytes=peer_uuid_bytes)

                print("NODE_MSG TYPE: {0}".format(msg_type))
                print("NODE_MSG PEER: {0}".format(peer_uuid))

                if type.decode('utf-8') == "SHOUT":
                    group_name = cmds.pop(0)
                    print("NODE_MSG GROUP: {0}".format(group_name))
                elif msg_type.decode('utf-8') == "ENTER":
		    headers = json.loads(cmds.pop(0))
		    print("NODE_MSG HEADERS: {0}".format(headers))
                print("NODE_MSG CONT: {0}".format(cmds))

        n.stop()
    # end chat_task


    if __name__ == '__main__':
        ctx = zmq.Context()
        chat_pipe = zhelper.zthread_fork(ctx, chat_task)

        while True:
            try:
                msg = input()
                chat_pipe.send(msg.encode('utf_8'))

            except (KeyboardInterrupt, SystemExit):
                break

        chat_pipe.send("$$STOP".encode('utf_8'))

        print("FINISHED")
```

Look at the [ZOCP](https://github.com/z25/pyZOCP) project for examples of how Pyre can be 
integrated into different environments and frameworks, i.e.:
- [Urwid](https://github.com/z25/pyZOCP/blob/master/examples/urwZOCP.py)
- [Blender](https://github.com/z25/pyZOCP/blob/master/examples/BpyZOCP.py)
- [Glib](https://github.com/z25/pyZOCP/blob/master/examples/glib_node.py)
- [QT](https://github.com/z25/pyZOCP/blob/master/examples/qt_ui_node.py)


Pyre uses the [Python Logging](https://docs.python.org/3.4/library/logging.html) module.
To change the debug level:

```
    # Create a StreamHandler for debugging
    logger = logging.getLogger("pyre")
    logger.setLevel(logging.INFO)
    # i.e. logging.DEBUG, logging.WARNING
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False

```

## Requirements

Python only needs PyZMQ. On some older versions of Python 
it also needs the [ipaddress](https://docs.python.org/3.4/library/ipaddress.html?highlight=ipaddress#module-ipaddress) module.

The recommended Python version is 3.3+


## Project Organization

Pyre is owned by all its authors and contributors. This is an open source
project licensed under the LGPLv3. To contribute to Zyre please read the
[C4.1 process](http://rfc.zeromq.org/spec:22) that we use.

To report an issue, use the [PYRE issue tracker](https://github.com/zeromq/pyre/issues) at github.com.
