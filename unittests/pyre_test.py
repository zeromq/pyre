import unittest
import pyre
import zmq
import time

class PyreTest(unittest.TestCase):
    
    #def setUp(self, *args, **kwargs):
    #    print("setup")
        #if inst_count == 1:
        #ctx = zmq.Context()
        #self.node1 = pyre.Pyre(ctx)
        #self.node1.set_name("node1")
        #self.node2 = pyre.Pyre(ctx)
        #self.node2.set_name("node2")
        # give time for nodes to exchange
        #super(unittest.TestCase, self).__init__(*args, **kwargs)

    def tearDown(self):
        global inst_count
        if inst_count == 1:
            node1.stop()
            node2.stop()

    def test_B(self):
        self.assertTrue(True)

    def test_get_name(self):
        self.assertTrue("node1" == node1.get_name())
        self.assertTrue("node2" == node2.get_name())

    def test_get_peers(self):
        id1 = node1.get_uuid()
        peers = node2.get_peers()
        self.assertTrue(isinstance(peers, list))
        self.assertTrue(id1 in peers)

    def test_get_peer_address(self):
        id1 = node1.get_uuid()
        id2 = node2.get_uuid()
        self.assertTrue(isinstance(node1.get_peer_address(id2), str))
        self.assertTrue(isinstance(node2.get_peer_address(id1), str))

    def test_get_peer_header_value(self):
        id1 = node1.get_uuid()
        id2 = node2.get_uuid()
        self.assertTrue("1" == node1.get_peer_header_value(id2, "X-TEST"))
        self.assertTrue("1" == node2.get_peer_header_value(id1, "X-TEST"))

    def test_get_own_groups(self):
        node1.join("TEST")
        node2.join("TEST")
        # pyre works asynchronous so give some time to let changes disperse
        time.sleep(0.5)
        self.assertTrue("TEST" in node1.get_own_groups())
        self.assertTrue("TEST" in node2.get_own_groups())

    def test_get_peer_groups(self):
        self.assertTrue("TEST" in node1.get_peer_groups())
        self.assertTrue("TEST" in node1.get_peer_groups())

    def test_zfinal(self):
        global inst_count
        inst_count = 1
        self.assertTrue(True)

if __name__ == '__main__':
    inst_count = 0

    ctx = zmq.Context()
    node1 = pyre.Pyre(ctx)
    node1.set_header("X-TEST", "1")
    node1.set_name("node1")
    node2 = pyre.Pyre(ctx)
    node2.set_header("X-TEST", "1")
    node2.set_name("node2")
    node1.start()
    node2.start()
    time.sleep(1)
    try:
        unittest.main()
    except Exception as a:
        print(a)
