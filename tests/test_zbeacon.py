import unittest
#import pyre
import zmq
import time
import struct
import uuid
import logging
import socket
from pyre.zactor import ZActor
from pyre.zbeacon import ZBeacon

class ZBeaconTest(unittest.TestCase):
    
    def setUp(self, *args, **kwargs):
        ctx = zmq.Context()
        ctx = zmq.Context()
        # two beacon frames
        self.transmit1 = struct.pack('cccb16sH', b'Z', b'R', b'E',
                           1, uuid.uuid4().bytes,
                           socket.htons(9999))
        self.transmit2 = struct.pack('cccb16sH', b'Z', b'R', b'E',
                           1, uuid.uuid4().bytes,
                           socket.htons(9999))

        self.node1 = ZActor(ctx, ZBeacon)
        self.node1.send_unicode("VERBOSE")
        self.node1.send_unicode("CONFIGURE", zmq.SNDMORE)
        self.node1.send(struct.pack("I", 9999))
        print("Hostname 1:", self.node1.recv_unicode())

        self.node2 = ZActor(ctx, ZBeacon)
        self.node2.send_unicode("VERBOSE")
        self.node2.send_unicode("CONFIGURE", zmq.SNDMORE)
        self.node2.send(struct.pack("I", 9999))
        print("Hostname 2:", self.node2.recv_unicode())
    # end setUp

    def tearDown(self):
        self.node1.destroy()
        self.node2.destroy()
    # end tearDown

    def test_node1(self):
        self.node1.send_unicode("PUBLISH", zmq.SNDMORE)
        self.node1.send(self.transmit1)

    def test_node2(self):
        self.node2.send_unicode("PUBLISH", zmq.SNDMORE)
        self.node2.send(self.transmit2)

    def test_recv_beacon1(self):
        self.node1.send_unicode("PUBLISH", zmq.SNDMORE)
        self.node1.send(self.transmit1)
        self.node2.send_unicode("PUBLISH", zmq.SNDMORE)
        self.node2.send(self.transmit2)
        req = self.node1.recv_multipart()
        self.assertEqual(self.transmit2, req[1])
    
    def test_recv_beacon1(self):
        self.node1.send_unicode("PUBLISH", zmq.SNDMORE)
        self.node1.send(self.transmit1)
        self.node2.send_unicode("PUBLISH", zmq.SNDMORE)
        self.node2.send(self.transmit2)
        req = self.node2.recv_multipart()
        self.assertEqual(self.transmit1, req[1])

# end ZBeaconTest

if __name__ == '__main__':

    #print(logging.Logger.manager.loggerDict)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    logging.getLogger("pyre.zbeacon2").setLevel(logging.DEBUG)
    
    try:
        unittest.main()
    except Exception as a:
        print(a)
