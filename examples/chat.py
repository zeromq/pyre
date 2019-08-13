try:
    from zyre_pyzmq import Zyre as Pyre
except Exception as e:
    print("using Python native module", e)
    from pyre import Pyre

from pyre import zhelper
import zmq
import json
import logging
import sys
import uuid

try:
    raw_input          # Python 2
except NameError:
    raw_input = input  # Python 3

def chat_task(ctx, pipe):
    n = Pyre("CHAT")
    n.set_header("CHAT_Header1","example header1")
    n.set_header("CHAT_Header2","example header2")
    n.join("CHAT")
    n.start()

    poller = zmq.Poller()
    poller.register(pipe, zmq.POLLIN)
    print(n.socket())
    poller.register(n.socket(), zmq.POLLIN)
    print(n.socket())
    while(True):
        items = dict(poller.poll())
        print(n.socket(), items)
        if pipe in items and items[pipe] == zmq.POLLIN:
            message = pipe.recv()
            # message to quit
            if message.decode('utf-8') == "$$STOP":
                break
            print("CHAT_TASK: %s" % message)
            n.shouts("CHAT", message.decode('utf-8'))
        else:
        #if n.socket() in items and items[n.socket()] == zmq.POLLIN:
            cmds = n.recv()
            msg_type = cmds.pop(0)
            print("NODE_MSG TYPE: %s" % msg_type)
            print("NODE_MSG PEER: %s" % uuid.UUID(bytes=cmds.pop(0)))
            print("NODE_MSG NAME: %s" % cmds.pop(0))
            if msg_type.decode('utf-8') == "SHOUT":
                print("NODE_MSG GROUP: %s" % cmds.pop(0))
            elif msg_type.decode('utf-8') == "ENTER":
                headers = json.loads(cmds.pop(0).decode('utf-8'))
                print("NODE_MSG HEADERS: %s" % headers)
                for key in headers:
                    print("key = {0}, value = {1}".format(key, headers[key]))
            print("NODE_MSG CONT: %s" % cmds)
    n.stop()


if __name__ == '__main__':
    # Create a StreamHandler for debugging
    logger = logging.getLogger("pyre")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False

    ctx = zmq.Context()
    chat_pipe = zhelper.zthread_fork(ctx, chat_task)

    while True:
        try:
            msg = raw_input()
            chat_pipe.send(msg.encode('utf_8'))
        except (KeyboardInterrupt, SystemExit):
            break
    chat_pipe.send("$$STOP".encode('utf_8'))
    print("FINISHED")
