""" These are the zre_msg messages
    HELLO - Greet a peer so it can connect back to us
        sequence      number 2
        ipaddress     string
        mailbox       number 2
        groups        strings
        status        number 1
        headers       dictionary
    WHISPER - Send a message to a peer
        sequence      number 2
        content       frame
    SHOUT - Send a message to a group
        sequence      number 2
        group         string
        content       frame
    JOIN - Join a group
        sequence      number 2
        group         string
        status        number 1
    LEAVE - Leave a group
        sequence      number 2
        group         string
        status        number 1
    PING - Ping a peer that has gone silent
        sequence      number 2
    PING_OK - Reply to a peer's ping
        sequence      number 2
"""

import struct

STRING_MAX = 255

class ZreMsg(object):

    VERSION = 1
    HELLO   = 1
    WHISPER = 2
    SHOUT   = 3
    JOIN    = 4
    LEAVE   = 5
    PING    = 6
    PING_OK = 7

    def __init__(self, id, data, *args, **kwargs):
        self.address = ""
        self.id = id
        self.sequence = 0
        self.mailbox = 0
        self.groups = ()
        self.status = 0
        self.headers = ""
        self.content = ""
        self.data = data
        self._needle =  0
        self._ceil = len(data)

    #def __del__(self):

    def recv(self, input):
        pass
    
    # Send the zre_msg to the output, and destroy it
    def send(self, output):
        pass
        #if self.id == ZreMsg.HELLO:

    
    # Send the HELLO to the output in one step
    def send_hello(self, output, sequence, ipaddress, mailbox, groups, status, headers):
        pass
    
    # Send the WHISPER to the output in one step
    def send_whisper(self, output, sequence, content):
        pass
    
    # Send the SHOUT to the output in one step
    def send_shout(self, output, sequence, group, content):
        pass
    
    # Send the JOIN to the output in one step
    def send_join(self, output, sequence, group, status):
        pass
    
    # Send the LEAVE to the output in one step
    def send_leave(self, sequence, group, status):
        pass
    
    # Send the PING to the output in one step
    def send_ping(self, output, sequence):
        pass
    
    #  Send the PING_OK to the output in one step
    def send_ping_ok(self, output, sequence):
        pass
    
    # Duplicate the zre_msg message
    def dup(self):
        pass
    
    # Print contents of message to stdout
    def dump(self):
        pass
    
    # Get/set the message address
    def get_address(self):
        pass
    
    def set_address(self, address):
        pass
    
    # Get the zre_msg id and printable command
    def get_id(self):
        pass
    
    def set_id(self, id):
        pass
    
    def command(self):
        pass
    
    # Get/set the sequence field
    def get_sequence(self):
        pass
    
    def set_sequence(self, sequence):
        pass
    
    # Get/set the ipaddress field
    def get_ipaddress(self):
        pass
    
    def set_ipaddress(self, ipaddress):
        pass
    
    # Get/set the mailbox field
    def get_mailbox(self):
        pass
    
    def set_mailbox(self):
        pass
    
    # Get/set the groups field
    def get_groups(self):
        pass
    
    def set_groups(self, groups):
        pass
    
    # Iterate through the groups field, and append a groups value
    # TODO: do we need this in python? l186 zre_msg.h
    
    #  Get/set the status field
    def get_status(self):
        pass
    
    def set_status(self, status):
        pass
    
    # Get/set the headers field
    def get_headers(self):
        pass
    
    def set_headers(self):
        pass
    
    # Get/set a value in the headers dictionary
    # TODO: l208 zre_msg.h
    
    # Get/set the group field
    def get_group(self):
        pass
    
    def set_group(self, group):
        pass

    def _get_string(self):
        s_len = self._get_number1()
        print(s_len)
        s = struct.unpack_from(str(s_len)+'s', self.data , offset=self._needle)
        self._needle += struct.calcsize('s'* s_len)
        return s[0].decode('UTF-8')
    
    def _get_number1(self):
        num = struct.unpack_from('b', self.data , offset=self._needle)
        self._needle += struct.calcsize('b')
        return num[0] 

    def _get_number2(self):
        num = struct.unpack_from('H', self.data , offset=self._needle)
        self._needle += struct.calcsize('H')
        return num[0]

    def _get_number4(self):
        num = struct.unpack_from('I', self.data , offset=self._needle)
        self._needle += struct.calcsize('I')
        return num[0]

    def _get_number8(self):
        num = struct.unpack_from('Q', self.data , offset=self._needle)
        self._needle += struct.calcsize('Q')
        return num[0]
    
    def _zre_dictstring_to_dict(self, s):
        l = s.split("=")
        return { l[0]: l[1] }

    def unpack_hello(self):
        """unpack a zre hello packet
        
        sequence      number 2
        ipaddress     string
        mailbox       number 2
        groups        strings
        status        number 1
        headers       dictionary
        
        """
        sequence = self._get_number2()
        print(sequence)
        print("needle is at: %i"% self._needle )
        ipaddress = self._get_string()
        print(ipaddress)
        print("needle is at: %i"% self._needle )
        mailbox = self._get_number2()
        print(mailbox)
        print("needle is at: %i"% self._needle )
        group_len = self._get_number1()
        print("needle is at: %i"% self._needle )
        print("grouplen: ", group_len)
        groups = []
        for x in range(group_len):
            groups.append(self._get_string())
        print(groups)
        print("post_group: needle is at: %i"% self._needle )
        status = self._get_number1()
        headers_len = self._get_number1()
        headers = {}
        for x in range(headers_len):
            hdr_item = self._get_string()
            headers.update(self._zre_dictstring_to_dict(hdr_item))
            #import ast
            #for hdr in hdrlist:
            #    # TODO: safer to use ast.literal_eval
            #    headers.update(ast.literal_eval(hdr))
        print(headers)

if __name__ == '__main__':
    testdata = struct.pack('Hb3sHbb2sb2sb2sbbb3sb3s',
                           11,       # sequence
                           3,        # str length 
                           b"192",   # ipaddress
                           20123,    # mailbox
                           3,        # groups len
                           2,b"g1",  # length + groupname
                           2,b"g2",  # length + groupname
                           2,b"g3",  # length + groupname
                           4,        # status
                           2,        # header len
                           3,b"a=z", # length + dict
                           3,b"b=x"  # length + dict
                           )
    m = ZreMsg(ZreMsg.HELLO, testdata)
    m.unpack_hello()
