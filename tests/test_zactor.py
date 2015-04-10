import unittest
import zmq
import logging
from pyre import zactor
from pyre.zactor import ZActor
from pyre.zbeacon import ZBeacon

class ZBeaconTest(unittest.TestCase):
    
    def setUp(self, *args, **kwargs):
        ctx = zmq.Context()
        self.actor = ZActor(ctx, zactor.echo_actor, "Hello, World")
    # end setUp

    def tearDown(self):
        self.actor.destroy()
    # end tearDown

    def test_echo(self):
        self.actor.send_multipart((b"ECHO", b"This is a string"))
        msg = self.actor.recv()
        self.assertEqual(b"This is a string", msg)
# end ZActorTest


if __name__ == '__main__':
    #print(logging.Logger.manager.loggerDict)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    logging.getLogger("pyre.zactor").setLevel(logging.DEBUG)
    
    try:
        unittest.main()
    except Exception as a:
        print(a)
