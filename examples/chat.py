from pyre import Pyre 
from pyre import zhelper 
import zmq 
import uuid
import logging


def chat_task(ctx, pipe):
    n = Pyre(ctx)
    #n.start()
    n.join("CHAT")

    poller = zmq.Poller()
    poller.register(pipe, zmq.POLLIN)
    poller.register(n.get_socket(), zmq.POLLIN)
    while(True):
        items = dict(poller.poll())
        if pipe in items and items[pipe] == zmq.POLLIN:
            message = pipe.recv()
            # message to quit
            if message.decode('utf-8') == "$$STOP":
                break
            print("CHAT_TASK: %s" % message)
            n.shout("CHAT", message)
        if n.get_socket() in items and items[n.get_socket()] == zmq.POLLIN:
            cmds = n.get_socket().recv_multipart()
            type = cmds.pop(0)
            print("NODE_MSG TYPE: %s" % type)
            print("NODE_MSG PEER: %s" % uuid.UUID(bytes=cmds.pop(0)))
            print("NODE_MSG NAME: %s" % cmds.pop(0))
            if type.decode('utf-8') == "SHOUT":
                print("NODE_MSG GROUP: %s" % cmds.pop(0))
            print("NODE_MSG CONT: %s" % cmds)
    n.stop()


if __name__ == '__main__':
    # Create a StreamHandler for debugging
    logger = logging.getLogger("pyre")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False

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
