import binascii
import itertools
import os
import random
import sys
import threading
import zmq
from . import zsocket

try:
    u = unicode
except NameError:
    u = str


# --------------------------------------------------------------------------
# Create a pipe, which consists of two PAIR sockets connected over inproc.
# The pipe is configured to use a default 1000 hwm setting. Returns the
# frontend and backend sockets.
def zcreate_pipe(ctx, hwm=1000):
    backend = zsocket.ZSocket(ctx, zmq.PAIR)
    frontend = zsocket.ZSocket(ctx, zmq.PAIR)
    backend.set_hwm(hwm)
    frontend.set_hwm(hwm)
    # close immediately on shutdown
    backend.setsockopt(zmq.LINGER, 0)
    frontend.setsockopt(zmq.LINGER, 0)

    endpoint = "inproc://zactor-%04x-%04x\n"\
                 %(random.randint(0, 0x10000), random.randint(0, 0x10000))
    while True:
        try:
            frontend.bind(endpoint)
        except:
            endpoint = "inproc://zactor-%04x-%04x\n"\
                 %(random.randint(0, 0x10000), random.randint(0, 0x10000))
        else:
            break
    backend.connect(endpoint)
    return (frontend, backend)


def zthread_fork(ctx, func, *args, **kwargs):
    """
    Create an attached thread. An attached thread gets a ctx and a PAIR
    pipe back to its parent. It must monitor its pipe, and exit if the
    pipe becomes unreadable. Returns pipe, or NULL if there was an error.
    """
    a = ctx.socket(zmq.PAIR)
    a.setsockopt(zmq.LINGER, 0)
    a.setsockopt(zmq.RCVHWM, 100)
    a.setsockopt(zmq.SNDHWM, 100)
    a.setsockopt(zmq.SNDTIMEO, 5000)
    a.setsockopt(zmq.RCVTIMEO, 5000)
    b = ctx.socket(zmq.PAIR)
    b.setsockopt(zmq.LINGER, 0)
    b.setsockopt(zmq.RCVHWM, 100)
    b.setsockopt(zmq.SNDHWM, 100)
    b.setsockopt(zmq.SNDTIMEO, 5000)
    b.setsockopt(zmq.RCVTIMEO, 5000)
    iface = "inproc://%s" % binascii.hexlify(os.urandom(8))
    a.bind(iface)
    b.connect(iface)

    thread = threading.Thread(target=func, args=((ctx, b) + args), kwargs=kwargs)
    thread.daemon = False
    thread.start()

    return a


from ctypes import c_char, c_char_p
from ctypes import c_uint, c_uint8, c_uint16, c_uint32
from ctypes import c_short, c_ushort
from ctypes import c_void_p, pointer
from ctypes import CDLL, Structure, Union

from sys import platform
if platform.startswith("win") and sys.version.startswith("2"):
    import win_inet_pton
from socket import AF_INET, AF_INET6, inet_ntop
try:
    from socket import AF_PACKET
except ImportError:
    AF_PACKET = -1

if platform.startswith("darwin") or platform.startswith("freebsd"):
    AF_LINK = 18
    IFT_ETHER = 0x6

else:
    AF_LINK = -1
    IFT_ETHER = -1


def get_ifaddrs():
    """
    A method for retrieving info of the network interfaces.
    Returns a nested dictionary containing everything it found.
    {
      ifname:
      {
        familynr:
        {
          addr:
          netmask:
          etc...

    Found this at http://pastebin.com/wxjai3Mw with some modification to
    make it work on OSX.
    """
    if platform.startswith("win"):
        return get_win_ifaddrs()

    # getifaddr structs
    class ifa_ifu_u(Union):
        _fields_ = [
            ("ifu_broadaddr", c_void_p),
            ("ifu_dstaddr", c_void_p)
        ]

    class ifaddrs(Structure):
        _fields_ = [
            ("ifa_next", c_void_p),
            ("ifa_name", c_char_p),
            ("ifa_flags", c_uint),
            ("ifa_addr", c_void_p),
            ("ifa_netmask", c_void_p),
            ("ifa_ifu", ifa_ifu_u),
            ("ifa_data", c_void_p)
        ]

    # AF_UNKNOWN / generic
    if platform.startswith("darwin") or platform.startswith("freebsd"):
        class sockaddr(Structure):
            _fields_ = [
                ("sa_len", c_uint8),
                ("sa_family", c_uint8),
                ("sa_data", (c_uint8 * 14))
            ]

    else:
        class sockaddr(Structure):
            _fields_ = [
                ("sa_family", c_uint16),
                ("sa_data", (c_uint8 * 14))
            ]

    # AF_INET / IPv4
    class in_addr(Union):
        _fields_ = [
            ("s_addr", c_uint32),
        ]

    if platform.startswith("darwin") or platform.startswith("freebsd"):
        class sockaddr_in(Structure):
            _fields_ = [
                ("sin_len", c_uint8),
                ("sin_family", c_uint8),
                ("sin_port", c_ushort),
                ("sin_addr", in_addr),
                ("sin_zero", (c_char * 8))  # padding
            ]
    else:
        class sockaddr_in(Structure):
            _fields_ = [
                ("sin_family", c_short),
                ("sin_port", c_ushort),
                ("sin_addr", in_addr),
                ("sin_zero",  (c_char * 8))  # padding
            ]

    # AF_INET6 / IPv6
    class in6_u(Union):
        _fields_ = [
            ("u6_addr8", (c_uint8 * 16)),
            ("u6_addr16", (c_uint16 * 8)),
            ("u6_addr32", (c_uint32 * 4))
        ]

    class in6_addr(Union):
        _fields_ = [
            ("in6_u", in6_u),
        ]

    if platform.startswith("darwin") or platform.startswith("freebsd"):
        class sockaddr_in6(Structure):
            _fields_ = [
                ("sin6_len", c_uint8),
                ("sin6_family", c_uint8),
                ("sin6_port", c_ushort),
                ("sin6_flowinfo", c_uint32),
                ("sin6_addr", in6_addr),
                ("sin6_scope_id", c_uint32),
            ]
    else:
        class sockaddr_in6(Structure):
            _fields_ = [
                ("sin6_family", c_short),
                ("sin6_port", c_ushort),
                ("sin6_flowinfo", c_uint32),
                ("sin6_addr", in6_addr),
                ("sin6_scope_id", c_uint32),
            ]

    # AF_PACKET / Linux
    class sockaddr_ll(Structure):
        _fields_ = [
            ("sll_family", c_uint16),
            ("sll_protocol", c_uint16),
            ("sll_ifindex", c_uint32),
            ("sll_hatype", c_uint16),
            ("sll_pktype", c_uint8),
            ("sll_halen", c_uint8),
            ("sll_addr", (c_uint8 * 8))
        ]

    # AF_LINK / BSD|OSX
    class sockaddr_dl(Structure):
        _fields_ = [
            ("sdl_len", c_uint8),
            ("sdl_family", c_uint8),
            ("sdl_index", c_uint16),
            ("sdl_type", c_uint8),
            ("sdl_nlen", c_uint8),
            ("sdl_alen", c_uint8),
            ("sdl_slen", c_uint8),
            ("sdl_data", (c_uint8 * 46))
        ]

    if platform.startswith("darwin"):
        libc = CDLL("libSystem.dylib")

    elif platform.startswith("freebsd"):
        libc = CDLL("libc.so")

    else:
        libc = CDLL("libc.so.6")

    ptr = c_void_p(None)
    result = libc.getifaddrs(pointer(ptr))
    if result:
        return None
    ifa = ifaddrs.from_address(ptr.value)
    result = []

    while ifa:
        # Python 2 gives us a string, Python 3 an array of bytes
        if type(ifa.ifa_name) is str:
            name = ifa.ifa_name
        else:
            name = ifa.ifa_name.decode()

        if ifa.ifa_addr:
            sa = sockaddr.from_address(ifa.ifa_addr)
        
            data = {}

            if sa.sa_family == AF_INET:
                if ifa.ifa_addr is not None:
                    si = sockaddr_in.from_address(ifa.ifa_addr)
                    data['addr'] = inet_ntop(AF_INET, si.sin_addr)

                if ifa.ifa_netmask is not None:
                    si = sockaddr_in.from_address(ifa.ifa_netmask)
                    data['netmask'] = inet_ntop(AF_INET, si.sin_addr)

                # check if a valid broadcast address is set and retrieve it
                # 0x2 == IFF_BROADCAST
                if ifa.ifa_flags & 0x2:
                    si = sockaddr_in.from_address(ifa.ifa_ifu.ifu_broadaddr)
                    data['broadcast'] = inet_ntop(AF_INET, si.sin_addr)

            if sa.sa_family == AF_INET6:
                if ifa.ifa_addr is not None:
                    si = sockaddr_in6.from_address(ifa.ifa_addr)
                    data['addr'] = inet_ntop(AF_INET6, si.sin6_addr)

                    if data['addr'].startswith('fe80:'):
                        data['scope'] = si.sin6_scope_id

                if ifa.ifa_netmask is not None:
                    si = sockaddr_in6.from_address(ifa.ifa_netmask)
                    data['netmask'] = inet_ntop(AF_INET6, si.sin6_addr)

            if sa.sa_family == AF_PACKET:
                if ifa.ifa_addr is not None:
                    si = sockaddr_ll.from_address(ifa.ifa_addr)
                    addr = ""
                    total = 0
                    for i in range(si.sll_halen):
                        total += si.sll_addr[i]
                        addr += "%02x:" % si.sll_addr[i]
                    addr = addr[:-1]
                    if total > 0:
                        data['addr'] = addr

            if sa.sa_family == AF_LINK:
                dl = sockaddr_dl.from_address(ifa.ifa_addr)

                if dl.sdl_type == IFT_ETHER:
                    addr = ""
                    for i in range(dl.sdl_alen):
                        addr += "%02x:" % dl.sdl_data[dl.sdl_nlen + i]

                    addr = addr[:-1]
                    data['addr'] = addr

            if len(data) > 0:
                iface = {}
                for interface in result:
                    if name in interface.keys():
                        iface = interface
                        break
                if iface:
                    iface[name][sa.sa_family] = data
                else:
                    iface[name] = { sa.sa_family : data }
                    result.append(iface)

        if ifa.ifa_next:
            ifa = ifaddrs.from_address(ifa.ifa_next)
        else:
            break

    libc.freeifaddrs(ptr)
    return result

def get_win_ifaddrs():
    """
    A method for retrieving info of the network
    interfaces. Returns a nested dictionary of
    interfaces in Windows.
    """
    # based on code from jaraco and many other attempts
    # on internet.
    # Fixed by <@gpotter2> from scapy's implementation to
    # add IPv6 support + fix structures

    import ctypes
    import struct
    import ipaddress
    import ctypes.wintypes
    from ctypes.wintypes import DWORD, WCHAR, BYTE, BOOL
    from socket import AF_INET
    
    # from iptypes.h
    MAX_ADAPTER_ADDRESS_LENGTH = 8
    MAX_DHCPV6_DUID_LENGTH = 130

    GAA_FLAG_INCLUDE_PREFIX = ctypes.c_ulong(0x0010)
    
    class in_addr(Structure):
        _fields_ = [("byte", ctypes.c_ubyte * 4)]


    class in6_addr(ctypes.Structure):
        _fields_ = [("byte", ctypes.c_ubyte * 16)]


    class sockaddr_in(ctypes.Structure):
        _fields_ = [("sin_family", ctypes.c_short),
                    ("sin_port", ctypes.c_ushort),
                    ("sin_addr", in_addr),
                    ("sin_zero", 8 * ctypes.c_char)]


    class sockaddr_in6(ctypes.Structure):
        _fields_ = [("sin6_family", ctypes.c_short),
                    ("sin6_port", ctypes.c_ushort),
                    ("sin6_flowinfo", ctypes.c_ulong),
                    ("sin6_addr", in6_addr),
                    ("sin6_scope_id", ctypes.c_ulong)]


    class SOCKADDR_INET(ctypes.Union):
        _fields_ = [("Ipv4", sockaddr_in),
                    ("Ipv6", sockaddr_in6),
                    ("si_family", ctypes.c_short)]
    LPSOCKADDR_INET = ctypes.POINTER(SOCKADDR_INET)

    class SOCKET_ADDRESS(ctypes.Structure):
        _fields_ = [
            ('address', LPSOCKADDR_INET),
            ('length', ctypes.c_int),
            ]

    class _IP_ADAPTER_ADDRESSES_METRIC(ctypes.Structure):
        _fields_ = [
            ('length', ctypes.c_ulong),
            ('interface_index', DWORD),
            ]

    class _IP_ADAPTER_ADDRESSES_U1(ctypes.Union):
        _fields_ = [
            ('alignment', ctypes.c_ulonglong),
            ('metric', _IP_ADAPTER_ADDRESSES_METRIC),
            ]

    class IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
        pass
    PIP_ADAPTER_UNICAST_ADDRESS = ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)
    IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
            ("length", ctypes.c_ulong),
            ("flags", DWORD),
            ("next", PIP_ADAPTER_UNICAST_ADDRESS),
            ("address", SOCKET_ADDRESS),
            ("prefix_origin", ctypes.c_int),
            ("suffix_origin", ctypes.c_int),
            ("dad_state", ctypes.c_int),
            ("valid_lifetime", ctypes.c_ulong),
            ("preferred_lifetime", ctypes.c_ulong),
            ("lease_lifetime", ctypes.c_ulong),
            ("on_link_prefix_length", ctypes.c_ubyte)
            ]

    class IP_ADAPTER_PREFIX(ctypes.Structure):
        pass
    PIP_ADAPTER_PREFIX = ctypes.POINTER(IP_ADAPTER_PREFIX)
    IP_ADAPTER_PREFIX._fields_ = [
        ("alignment", ctypes.c_ulonglong),
        ("next", PIP_ADAPTER_PREFIX),
        ("address", SOCKET_ADDRESS),
        ("prefix_length", ctypes.c_ulong)
        ]

    class IP_ADAPTER_ADDRESSES(ctypes.Structure):
        pass
    LP_IP_ADAPTER_ADDRESSES = ctypes.POINTER(IP_ADAPTER_ADDRESSES)
    
    # for now, just use void * for pointers to unused structures
    PIP_ADAPTER_ANYCAST_ADDRESS = ctypes.c_void_p
    PIP_ADAPTER_MULTICAST_ADDRESS = ctypes.c_void_p
    PIP_ADAPTER_DNS_SERVER_ADDRESS = ctypes.c_void_p
    #PIP_ADAPTER_PREFIX = ctypes.c_void_p
    PIP_ADAPTER_WINS_SERVER_ADDRESS_LH = ctypes.c_void_p
    PIP_ADAPTER_GATEWAY_ADDRESS_LH = ctypes.c_void_p
    PIP_ADAPTER_DNS_SUFFIX = ctypes.c_void_p

    IF_OPER_STATUS = ctypes.c_uint # this is an enum, consider http://code.activestate.com/recipes/576415/
    IF_LUID = ctypes.c_uint64

    NET_IF_COMPARTMENT_ID = ctypes.c_uint32
    GUID = ctypes.c_byte*16
    NET_IF_NETWORK_GUID = GUID
    NET_IF_CONNECTION_TYPE = ctypes.c_uint # enum
    TUNNEL_TYPE = ctypes.c_uint # enum

    IP_ADAPTER_ADDRESSES._fields_ = [
        ('length', ctypes.c_ulong),
        ('interface_index', DWORD),
        ('next', LP_IP_ADAPTER_ADDRESSES),
        ('adapter_name', ctypes.c_char_p),
        ('first_unicast_address', PIP_ADAPTER_UNICAST_ADDRESS),
        ('first_anycast_address', PIP_ADAPTER_ANYCAST_ADDRESS),
        ('first_multicast_address', PIP_ADAPTER_MULTICAST_ADDRESS),
        ('first_dns_server_address', PIP_ADAPTER_DNS_SERVER_ADDRESS),
        ('dns_suffix', ctypes.c_wchar_p),
        ('description', ctypes.c_wchar_p),
        ('friendly_name', ctypes.c_wchar_p),
        ('byte', BYTE * MAX_ADAPTER_ADDRESS_LENGTH),
        ('physical_address_length', DWORD),
        ('flags', DWORD),
        ('mtu', DWORD),
        ('interface_type', DWORD),
        ('oper_status', IF_OPER_STATUS),
        ('ipv6_interface_index', DWORD),
        ('zone_indices', DWORD * 16),
        ('first_prefix', PIP_ADAPTER_PREFIX),
        ('transmit_link_speed', ctypes.c_uint64),
        ('receive_link_speed', ctypes.c_uint64),
        ('first_wins_server_address', PIP_ADAPTER_WINS_SERVER_ADDRESS_LH),
        ('first_gateway_address', PIP_ADAPTER_GATEWAY_ADDRESS_LH),
        ('ipv4_metric', ctypes.c_ulong),
        ('ipv6_metric', ctypes.c_ulong),
        ('luid', IF_LUID),
        ('dhcpv4_server', SOCKET_ADDRESS),
        ('compartment_id', NET_IF_COMPARTMENT_ID),
        ('network_guid', NET_IF_NETWORK_GUID),
        ('connection_type', NET_IF_CONNECTION_TYPE),
        ('tunnel_type', TUNNEL_TYPE),
        ('dhcpv6_server', SOCKET_ADDRESS),
        ('dhcpv6_client_duid', ctypes.c_byte * MAX_DHCPV6_DUID_LENGTH),
        ('dhcpv6_client_duid_length', ctypes.c_ulong),
        ('dhcpv6_iaid', ctypes.c_ulong),
        ('first_dns_suffix', PIP_ADAPTER_DNS_SUFFIX),
        ]

    def GetAdaptersAddresses(af=0):
        """
        Returns an iteratable list of adapters.
        param:
         - af: the address family to read on
        """ 
        size = ctypes.c_ulong()
        AF_UNSPEC = 0
        flags = GAA_FLAG_INCLUDE_PREFIX
        GetAdaptersAddresses = ctypes.windll.iphlpapi.GetAdaptersAddresses
        GetAdaptersAddresses.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.POINTER(IP_ADAPTER_ADDRESSES),
            ctypes.POINTER(ctypes.c_ulong),
        ]
        GetAdaptersAddresses.restype = ctypes.c_ulong
        res = GetAdaptersAddresses(af, flags, None, None, size)
        if res != 0x6f: # BUFFER OVERFLOW -> populate size
            raise RuntimeError("Error getting structure length (%d)" % res)
        pointer_type = ctypes.POINTER(IP_ADAPTER_ADDRESSES)
        buffer = ctypes.create_string_buffer(size.value)
        struct_p = ctypes.cast(buffer, pointer_type)
        res = GetAdaptersAddresses(af, flags, None, struct_p, size)
        if res != 0x0: # NO_ERROR
            raise RuntimeError("Error retrieving table (%d)" % res)
        while struct_p:
            yield struct_p.contents
            struct_p = struct_p.contents.next

    result = []
    # In theory, we could use AF_UNSPEC = 0, but it doesn't work in practice
    for i in itertools.chain(GetAdaptersAddresses(AF_INET), GetAdaptersAddresses(AF_INET6)):
        #print("--------------------------------------")
        #print("IF: {0}".format(i.description))
        #print("\tdns_suffix: {0}".format(i.dns_suffix))
        #print("\tinterface type: {0}".format(i.interface_type))
        fu = i.first_unicast_address.contents
        ad = fu.address.address.contents
        #print("\tfamily: {0}".format(ad.family))
        if ad.si_family == AF_INET:
            ip_bytes = bytes(bytearray(ad.Ipv4.sin_addr))
            ip = ipaddress.IPv4Address(ip_bytes)
            ip_if = ipaddress.IPv4Interface(u("{0}/{1}".format(ip, fu.on_link_prefix_length)))
        elif ad.si_family == AF_INET6:
            ip_bytes = bytes(bytearray(ad.Ipv6.sin6_addr))
            ip = ipaddress.IPv6Address(ip_bytes)
            ip_if = ipaddress.IPv6Interface(u("{0}/{1}".format(ip, fu.on_link_prefix_length)))
        #print("\tipaddress: {0}".format(ip))
        #print("\tnetmask: {0}".format(ip_if.netmask))
        #print("\tnetwork: {0}".format(ip_if.network.network_address))
        #print("\tbroadcast: {0}".format(ip_if.network.broadcast_address))
        #print("\tmask length: {0}".format(fu.on_link_prefix_length))
        data = {}
        data['addr'] = "{0}".format(ip)
        data['netmask'] = "{0}".format(ip_if.netmask)
        data['broadcast'] = "{0}".format(ip_if.network.broadcast_address)
        data['network'] = "{0}".format(ip_if.network.network_address)

        name = i.description 
        #result[i.description] = { ad.family : d}
        iface = {}
        for interface in result:
            if name in interface.keys():
                iface = interface
                break
        if iface:
            iface[name][ad.si_family] = data
        else:
            iface[name] = { ad.si_family : data }
            result.append(iface)

    return result

