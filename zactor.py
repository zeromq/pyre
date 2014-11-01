# =========================================================================
# zactor - simple actor framework
# 
# Copyright (c) the Contributors as noted in the AUTHORS file.
# This file is part of CZMQ, the high-level C binding for 0MQ:
# http://czmq.zeromq.org.
# 
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# =========================================================================
# 
# 
# The zactor class provides a simple actor framework. It replaces the
# zthread class, which had a complex API that did not fit the CLASS
# standard. A CZMQ actor is implemented as a thread plus a PAIR-PAIR
# pipe. The constructor and destructor are always synchronized, so the
# caller can be sure all resources are created, and destroyed, when these
# calls complete. (This solves a major problem with zthread, that a caller
# could not be sure when a child thread had finished.)
# 
# A zactor_t instance acts like a zsock_t and you can pass it to any CZMQ
# method that would take a zsock_t argument, including methods in zframe,
# zmsg, zstr, zpoller, and zloop.

import random
import zmq
import threading
from . import zsocket

class ZActor(object):
    
    ZACTOR_TAG = 0x0005cafe

    def __init__(self, ctx, actor, *args, **kwargs):
        self.tag = self.ZACTOR_TAG
        self.ctx = ctx
        # Create front-to-back pipe pair
        self.pipe = zsocket.ZSocket(ctx, zmq.PAIR)
        self.shim_pipe = zsocket.ZSocket(ctx, zmq.PAIR)
        # TODO: set HWM
        self.pipe.set_hwm(1000)
        self.shim_pipe.set_hwm(1000)
        #  Now bind and connect pipe ends
        self.endpoint = "inproc://zactor-%04x-%04x\n"\
                 %(random.randint(0, 0x10000), random.randint(0, 0x10000))
        self.pipe.bind(self.endpoint)
        self.shim_pipe.connect(self.endpoint)
        self.shim_handler = actor
        self.shim_args = args

        self.thread = threading.Thread(target=actor, args=(self.ctx, self.shim_pipe)+args, kwargs=kwargs)
        #self.thread.daemon = True
        self.thread.start()

        # Mandatory handshake for new actor so that constructor returns only
        # when actor has also initialized. This eliminates timing issues at
        # application start up.
        self.pipe.wait()

    def destroy(self):
        # Signal the actor to end and wait for the thread exit code
        # If the pipe isn't connected any longer, assume child thread
        # has already quit due to other reasons and don't collect the
        # exit signal.
        self.pipe.set(zmq.SNDTIMEO, 0)
        self.pipe.send_unicode("$TERM")
        # misschien self.pipe.wait()????
        self.pipe.wait()
        self.pipe.close()
        self.tag = 0xDeadBeef;

    def send(self, *args, **kwargs):
        self.pipe.send(*args, **kwargs)

    def send_unicode(self, *args, **kwargs):
        self.pipe.send_unicode(*args, **kwargs)

    def recv(self, *args, **kwargs):
        return self.pipe.recv(*args, **kwargs)

    def recv_multipart(self, *args, **kwargs):
        return self.pipe.recv_multipart(*args, **kwargs)

    # --------------------------------------------------------------------------
    # Probe the supplied object, and report if it looks like a zactor_t.
    def is_zactor(self):
        return isinstance(ZActor, self)

    # --------------------------------------------------------------------------
    # Probe the supplied reference. If it looks like a zactor_t instance,
    # return the underlying libzmq actor handle; else if it looks like
    # a libzmq actor handle, return the supplied value.
    # In Python we just return the pipe socket
    def resolve(self):
        return self.pipe

def echo_actor(pipe, *args):
    # Do some initialization
    pipe.signal()
    terminated = False;
    while not terminated:
        msg = pipe.recv_multipart();
        command = msg.pop(0)
        if command == b"$TERM":
            terminated = True
        elif command == b"ECHO":
            pipe.send(msg.pop(0))
        else:
            print("E: invalid message to actor")
    pipe.signal()


def zactor_test(verbose=False):
    print(" * zactor: ")
    actor = ZActor(zmq.Context(), echo_actor, "Hello, World")
    actor.send_unicode("ECHO", zmq.SNDMORE)
    actor.send_unicode("This is a string")
    msg = actor.recv()
    print("RECEIVED: %s" %msg)
    actor.destroy()
    print("OK");

if __name__ == '__main__':
    zactor_test()
