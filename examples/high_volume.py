import logging
import time

import zmq

from pyre import Pyre
from pyre import zhelper


def chat_task(ctx, pipe, ncmds):
    n = Pyre(ctx)
    n.join("CHAT")
    n.start()

    # wait for someone else to join the chat
    while not n.get_peer_groups():
        pass

    pipe.send('ready'.encode('utf-8'))
    cmds = 0
    t0 = time.time()

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
            n.shout("CHAT", message)
        if n.inbox in items and items[n.inbox] == zmq.POLLIN:
            n.recv()
            cmds += 1
            if cmds == ncmds:
                msg = 'Got %s msgs in %0.2f sec' % (cmds, time.time() - t0)
                pipe.send(msg.encode('utf-8'))
    n.stop()


if __name__ == '__main__':
    # Create a StreamHandler for debugging
    logger = logging.getLogger("pyre")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False

    ctx = zmq.Context()
    ntasks = 1000
    chat_pipe = zhelper.zthread_fork(ctx, chat_task, ntasks)

    print("Waiting for Peer...")
    chat_pipe.recv()

    for i in range(ntasks):
        chat_pipe.send('hello'.encode('utf-8'))
        time.sleep(0.0001)

    print(chat_pipe.recv().decode('utf-8'))
    chat_pipe.send("$$STOP".encode('utf_8'))
    print("FINISHED")
