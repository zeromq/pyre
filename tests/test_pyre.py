import unittest
import pyre
import zmq
import time
import logging
import sys


if sys.version.startswith('3'):
    unicode = str


class PyreTest(unittest.TestCase):
    
    def setUp(self, *args, **kwargs):
        ctx = zmq.Context()
        self.node1 = pyre.Pyre(ctx)
        self.node1.set_header("X-TEST", "1")
        self.node1.set_name("node1")
        self.node2 = pyre.Pyre(ctx)
        self.node2.set_header("X-TEST", "1")
        self.node2.set_name("node2")
        self.node1.start()
        self.node2.start()
        # give time for nodes to exchange
        time.sleep(1)
    # end setUp

    def tearDown(self):
        self.node1.stop()
        self.node2.stop()
    # end tearDown

    def test_get_name(self):
        self.assertEqual("node1", self.node1.get_name())
        self.assertEqual("node2", self.node2.get_name())
    # end test_get_name

    def test_get_peers(self):
        id1 = self.node1.get_uuid()
        peers = self.node2.get_peers()

        self.assertIsInstance(peers, list)
        self.assertIn(id1, peers)
    # end test_get_peers

    def test_get_peer_address(self):
        id1 = self.node1.get_uuid()
        id2 = self.node2.get_uuid()

        self.assertIsInstance(self.node1.get_peer_address(id2), unicode)
        self.assertIsInstance(self.node2.get_peer_address(id1), unicode)
    # end test_get_peer_address

    def test_get_peer_header_value(self):
        id1 = self.node1.get_uuid()
        id2 = self.node2.get_uuid()

        self.assertEqual("1", self.node1.get_peer_header_value(id2, "X-TEST"))
        self.assertEqual("1", self.node2.get_peer_header_value(id1, "X-TEST"))
    # end test_get_peer_header_value

    def test_get_own_groups(self):
        self.node1.join("TEST")
        self.node2.join("TEST")
        # pyre works asynchronous so give some time to let changes disperse
        time.sleep(0.5)

        self.assertIn("TEST", self.node1.get_own_groups())
        self.assertIn("TEST", self.node2.get_own_groups())
    # end test_get_own_groups

    def test_join_leave_msg(self):
        msg = self.node1.recv_multipart()
        self.assertEqual(msg[0], b'ENTER')
        msg = self.node2.recv_multipart()
        self.assertEqual(msg[0], b'ENTER')
        self.node1.join("TEST")
        self.node2.join("TEST")
        msg = self.node1.recv_multipart()
        self.assertEqual(msg[0], b'JOIN')
        msg = self.node2.recv_multipart()
        self.assertEqual(msg[0], b'JOIN')
        self.node1.leave("TEST")
        self.node2.leave("TEST")
        msg = self.node1.recv_multipart()
        self.assertEqual(msg[0], b'LEAVE')
        msg = self.node2.recv_multipart()
        self.assertEqual(msg[0], b'LEAVE')

    def test_get_peer_groups(self):
        self.node1.join("TEST")
        self.node2.join("TEST")

        # pyre works asynchronous so give some time to let changes disperse
        time.sleep(0.5)

        self.assertIn("TEST", self.node1.get_peer_groups())
        self.assertIn("TEST", self.node2.get_peer_groups())
    # end test_get_peer_groups

    def test_whispers(self):
        msg = self.node1.recv_multipart()
        self.assertEqual(msg[0], b'ENTER')
        msg = self.node2.recv_multipart()
        self.assertEqual(msg[0], b'ENTER')
        self.node1.whispers(self.node2.get_uuid(), "Hi")
        msg = self.node2.recv_multipart()
        self.assertEqual(b"WHISPER", msg[0])
        self.assertEqual(self.node1.get_uuid().bytes, msg[1])
        self.assertEqual(b"node1", msg[2])
        self.assertEqual(b"Hi", msg[3])

    def test_shouts(self):
        msg = self.node1.recv_multipart()
        self.assertEqual(msg[0], b'ENTER')
        msg = self.node2.recv_multipart()
        self.assertEqual(msg[0], b'ENTER')
        self.node1.join("TEST")
        self.node2.join("TEST")
        msg = self.node1.recv_multipart()
        self.assertEqual(msg[0], b'JOIN')
        msg = self.node2.recv_multipart()
        self.assertEqual(msg[0], b'JOIN')
        self.node1.shouts("TEST", "Hi")
        msg = self.node2.recv_multipart()
        self.assertEqual(b"SHOUT", msg[0])
        self.assertEqual(self.node1.get_uuid().bytes, msg[1])
        self.assertEqual(b"node1", msg[2])
        self.assertEqual(b"TEST", msg[3])
        self.assertEqual(b"Hi", msg[4])

    def test_zfinal(self):
        global inst_count
        inst_count = 1
        self.assertTrue(True)
    # end test_zfinal
# end PyreTest

if __name__ == '__main__':
    inst_count = 0

    logger = logging.getLogger("pyre")
    logger.setLevel(logging.DEBUG)

    try:
        unittest.main()
    except Exception as a:
        print(a)
