import zmq
import threading
import binascii
import os

def zthread_fork(ctx, func, *args, **kwargs):
    """
    Create an attached thread. An attached thread gets a ctx and a PAIR
    pipe back to its parent. It must monitor its pipe, and exit if the
    pipe becomes unreadable. Returns pipe, or NULL if there was an error.
    """
    a = ctx.socket(zmq.PAIR)
    a.linger = 0
    b = ctx.socket(zmq.PAIR)
    b.linger = 0
    a.set_hwm(1)
    b.set_hwm(1)
    iface = "inproc://%s" % binascii.hexlify(os.urandom(8))
    a.bind(iface)
    b.connect(iface)

    thread = threading.Thread(target=func, args=((ctx, b)+args), kwargs=kwargs)
    thread.daemon = True
    thread.start()

    return a