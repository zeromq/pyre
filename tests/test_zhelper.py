import unittest
from pyre import zhelper
from pyre import zbeacon
import zmq
import time

class ZHelperTest(unittest.TestCase):
    
    def test_get_ifaddrs(self):
        ifs = zhelper.get_ifaddrs()
        self.assertIsInstance(ifs, list)
        self.assertIsInstance(ifs[0], dict)
    # end test_get_ifaddrs

    def test_get_ifaddrs_loopback(self):
        ifs = zhelper.get_ifaddrs()
        addrs = []
        for iface in ifs:
            #print(iface)
            for i,v in iface.items():
                #print(i,v)
                # 2 is for ipv4
                if v.get(2):
                    addrs.append(v[2]['addr'])
        self.assertIn('127.0.0.1', addrs)
    # end test_get_ifaddrs_loopback

# end ZHelperTest

if __name__ == '__main__':
    unittest.main()

