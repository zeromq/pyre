#   =========================================================================
#   zbeacon - LAN service announcement and discovery
#
#   -------------------------------------------------------------------------
#   Copyright (c) 1991-2013 iMatix Corporation <www.imatix.com>
#   Copyright other contributors as noted in the AUTHORS file.
# 
#   This file is part of PyZyre, the ZYRE Python implementation:
#   http://github.com/sphaero/pyzyre & http://czmq.zeromq.org.
# 
#   This is free software; you can redistribute it and/or modify it under
#   the terms of the GNU Lesser General Public License as published by the 
#   Free Software Foundation; either version 3 of the License, or (at your 
#   option) any later version.
#
#   This software is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABIL-
#   ITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General 
#   Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public License 
#   along with this program. If not, see <http://www.gnu.org/licenses/>.
#   =========================================================================
import socket
import zmq
import zhelper
import time
import struct
import ipaddress

BEACON_MAX      = 255
INTERVAL_DFLT   = 1000

class ZBeacon(object):

    def __init__(self, ctx, portNbr):
        self._ctx = ctx
        self._portNbr = portNbr
        # Start beacon background agent
        self._pipe = zhelper.zthread_fork(
                        self._ctx, 
                        ZBeaconAgent, 
                        self._portNbr,
                    )
        # Configure agent with arguments
        self._pipe.send_unicode("%d" %portNbr)
        # Agent replies with our host name
        self._hostname = self._pipe.recv_unicode()

    def __del__(self):
        self._pipe.send_unicode("TERMINATE")
        print("Terminating zbeacon")

    # Set broadcast interval in milliseconds (default is 1000 msec)
    def set_interval(self, interval=1000):
        self._pipe.send_unicode("INTERVAL", flags=zmq.SNDMORE)
        self._pipe.send_unicode(interval)

    # Filter out any beacon that looks exactly like ours
    def set_noecho(self):
        self._pipe.send_unicode("NOECHO")

    # Start broadcasting beacon to peers at the specified interval
    def publish(self, transmit):
        self._pipe.send_unicode("PUBLISH", flags=zmq.SNDMORE)
        #TODO
        self._pipe.send("transmitbla")

    # Stop broadcasting beacons
    def silence(self):
        self._pipe.send("SILENCE")

    # Start listening to other peers; zero-sized filter means get everything
    def subscribe(self, filter):
        self._pipe.send_unicode("SUBSCRIBE", flags=zmq.SNDMORE)
        #TODO What in filter??
        self._pipe.send(self._filter)

    # Stop listening to other peers
    def unsubscribe(self, filter):
        self._pipe.send_unicode("UNSUBSCRIBE")

    # Get beacon ZeroMQ socket, for polling or receiving messages
    def get_socket(self):
        return self._pipe
    
    # Return our own IP address as printable string
    def get_hostname(self):
        return self._hostname


class ZBeaconAgent(object):

    def __init__(self, ctx, pipe, port, beaconAddress="255.255.255.255"):
        # Socket to talk back to application
        self._pipe = pipe
        # UDP socket for send/recv
        self._udpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # UDP port number we work on
        self._port = port
        # Beacon broadcast interval
        self._interval = 10
        # Are we broadcasting?
        self._enabled = True
        # Ignore own (unique) beacons?
        self._noEcho = True
        # API shut us down
        self._terminated = False
        # Next broadcast time
        self._pingAt = 0 #start bcast immediately
        # Beacon transmit data
        # struct.pack('cccb16sIb', b'Z',b'R',b'E', 1, uuid.bytes, self._portNbr, 1)
        self.transmit = "hello"
        # Beacon filter data
        self._filter = self.transmit #not used?
        # Our own address
        self.address = None
        # Our broadcast address, in case we do broascasting
        self.broadcast = '255.255.255.255'
        #byte announcement [2] = (port_nbr >> 8) & 0xFF, port_nbr & 0xFF
        try:
            if ipaddress.IPv4Address(beaconAddress).is_multicast:
                # TTL
                self._udpSock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                # TODO: This should only be used if we do not have inproc method! 
                self._udpSock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
                # Usually, the system administrator specifies the 
                # default interface multicast datagrams should be 
                # sent from. The programmer can override this and
                # choose a concrete outgoing interface for a given
                # socket with this option. 
                #
                # this results in the loopback address?
                # host = socket.gethostbyname(socket.gethostname())
                # self._udpSock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
                # You need to tell the kernel which multicast groups 
                # you are interested in. If no process is interested 
                # in a group, packets destined to it that arrive to 
                # the host are discarded.            
                # You can always fill this last member with the 
                # wildcard address (INADDR_ANY) and then the kernel 
                # will deal with the task of choosing the interface.
                #
                # Maximum memberships: /proc/sys/net/ipv4/igmp_max_memberships 
                # self._udpSock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, 
                #       socket.inet_aton("225.25.25.25") + socket.inet_aton(host))
                group = socket.inet_aton(beaconAddress)
                mreq = struct.pack('4sL', group, socket.INADDR_ANY)
                self._udpSock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, 
                       mreq)
                self._udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                self._udpSock.bind((beaconAddress, self._port))
                self._dstAddr = beaconAddress
            else:
                # Only for broadcast
                print("Setting up a broadcast beacon on %s:%s" %(self.broadcast, self._port))
                self._udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)       
                self._udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                self._udpSock.bind((self.broadcast, self._port))
                self._dstAddr = self.broadcast
        except socket.error as msg:
            print(msg)
        # Send our hostname back to AP
        # TODO This results in just the ip address
        self.address = socket.gethostbyname(socket.gethostname())
        self._pipe.send_unicode(self.address)
        self.run()

    def __del__(self):
        self._udpSock.close()

    def get_interface(self):
        # Get the actual network interface we're working on
        # Currently implemented for POSIX and for Windows
        # This is required for getting broadcastaddresses...
        # Subnet broadcast addresses don't work on some platforms but is
        # assumed to work if the interface is specified.
        # TODO
        pass

    def api_command(self):
        cmds = self._pipe.recv_multipart()
        print("ApiCommand: %s" %cmds)
        if str(cmds[0].decode('UTF-8')) == "INTERVAL":
            self._interval = atoi(cmds[1])
        if str(cmds[0].decode('UTF-8')) == "TERMINATE":
            self.transmit = "bye"
            self._terminated = True
            self._pipe.send_unicode("OK")
        else:
            print("E: unexpected API command '%s'"% cmds)

    def send(self):
        self._udpSock.sendto(self.transmit.encode(encoding='UTF-8'), (self._dstAddr, self._port))

    def recv(self):
        # do socket lees shit l.745
        # #define BEACON_MAX      255 //  Max size of beacon data
        try:
            data, addr = self._udpSock.recvfrom(255)
        except socket.error as e:
            print(e)
        # If noEcho is set, check if beacon is our own
        if self._noEcho:
            if self.transmit == data.decode('UTF-8'):
                print("this is our own beacon, ignoring")
                return
        # send the data onto the pipe
        self._pipe.send(data)

    def run(self):
        print("ZBeacon runnning")
        self.poller = zmq.Poller()
        self.poller.register(self._pipe, zmq.POLLIN)
        self.poller.register(self._udpSock, zmq.POLLIN)
        # not interrupted
        while(True):
            timeout = 1000
            if self.transmit:
                timeout = self._pingAt - time.time()
                if timeout < 0:
                    timeout = 0

            items = dict(self.poller.poll(timeout*1000))
            
            if self._pipe in items and items[self._pipe] == zmq.POLLIN:
                self.api_command()
                print("PIPED:")
            if self._udpSock.fileno() in items and items[self._udpSock.fileno()] == zmq.POLLIN:
                self.recv()
                print("RECV")

            if self.transmit and time.time() >= self._pingAt:
                self.send()
                self._pingAt = time.time() + self._interval

            if self._terminated:
                break
        print("ZBeaconAgent terminated")
        

def zbeacon_test(ctx, pipe):
    a = ZBeaconAgent(ctx, pipe, 1200)
            
if __name__ == '__main__':
    ctx = zmq.Context()
    beacon = ZBeacon(ctx, 1200)
    beacon_pipe = beacon.get_socket()
    while True:
        try:
            msg = beacon_pipe.recv()
            print("BEACONMSG: %s" %msg)
        except (KeyboardInterrupt, SystemExit):
            break
    print("FINISHED")
        