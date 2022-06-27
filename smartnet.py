#!/usr/bin/python

import socket
from threading import Timer,Thread

def shift_this(number, high_first=True):
    """Utility method: extracts MSB and LSB from number.

    Args:
    number - number to shift
    high_first - MSB or LSB first (true / false)

    Returns:
    (high, low) - tuple with shifted values

    """
    low = (number & 0xFF)
    high = ((number >> 8) & 0xFF)
    if high_first:
        return((high, low))
    return((low, high))


def put_in_range(number, range_min, range_max, make_even=True):
    """Utility method: sets number in defined range.
    DEPRECATED: this will be removed from the library"""

    number = max(range_min, min(number, range_max))
    if make_even:
        if number % 2 != 0:
            number += 1
    return number


def make_address_mask(universe, sub=0, net=0, is_simplified=True):
    """Returns the address bytes for a given universe, subnet and net.

    Args:
    universe - Universe to listen
    sub - Subnet to listen
    net - Net to listen
    is_simplified - Whether to use nets and subnet or universe only,
    see User Guide page 5 (Universe Addressing)

    Returns:
    bytes - byte mask for given address

    """
    def clamp(number, min_val, max_val):
        return max(min_val, min(number, max_val))
    
    def shift_this(number, high_first=True):
        low = (number & 0xFF)
        high = ((number >> 8) & 0xFF)
        if high_first:
            return((high, low))
        return((low, high))
        
    address_mask = bytearray()

    if is_simplified:
        # Ensure data is in right range
        universe =  clamp(universe, 0, 32767)

        # Make mask
        msb, lsb = shift_this(universe)  # convert to MSB / LSB
        address_mask.append(lsb)
        address_mask.append(msb)
    else:
        # Ensure data is in right range
        universe = clamp(universe, 0, 15)
        sub = clamp(sub, 0, 15)
        net = clamp(net, 0, 127)

        # Make mask
        address_mask.append(sub << 4 | universe)
        address_mask.append(net & 0xFF)

    return address_mask


class Smartnet():
    """(Very) simple implementation of Artnet."""

    UDP_PORT = 6454

    def __init__(self, target_ip='127.0.0.1', universes: list = [0],fps=40, broadcast=False):
        """Initializes Art-Net Client.

        Args:
        targetIP - IP of receiving device
        universes - universes to listen
        fps - transmition rate
        broadcast - whether to broadcast in local sub

        Returns:
        None

        """
        # Instance variables
        self.target_ip = target_ip
        self.sequence = 0
        self.subnet = 0
        self.net = 0
        self.header_list = list() # contains a header with every universe

        # UDP SOCKET
        self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if broadcast:
            self.socket_client.setsockopt(
                socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Timer
        self.fps = fps
        self.__clock = None

        #make set of headers for every universe
        universes.sort()
        i = 0
        for u in universes:
            if i == u:
                self.header_list.append(self.make_header_no_packetsize(self.net, self.subnet, u))
                i += 1
            else:
                while(i != u): # in case universes are skipped, so index matches with universe
                    self.header_list.append(None)
                    i += 1
                self.header_list.append(self.make_header_no_packetsize(self.net, self.subnet, u))
                i += 1
    
    
    def __del__(self):
        """Graceful shutdown."""
        self.stop()
        self.close()

    def __str__(self):
        """Printable object state."""
        state = "===================================\n"
        state += "Stupid Artnet initialized\n"
        state += f"Target IP: {self.target_ip} : {self.UDP_PORT} \n"
        state += f"Universe: {self.universe} \n"
        if not self.is_simplified:
            state += f"Subnet: {self.subnet} \n"
            state += f"Net: {self.net} \n"
        state += f"Packet Size: {self.packet_size} \n"
        state += "==================================="

        return state

    def make_header_no_packetsize(self, net: int, subnet: int, universe: int):
        """Creates Header to save in set and add packetsize dynamically."""
        # 0 - id (7 x bytes + Null)
        tmp = bytearray()
        tmp.extend(bytearray('Art-Net', 'utf8'))
        tmp.append(0x0)
        # 8 - opcode (2 x 8 low byte first)
        tmp.append(0x00)
        tmp.append(0x50)  # ArtDmx data packet
        # 10 - prototocol version (2 x 8 high byte first)
        tmp.append(0x0)
        tmp.append(14)
        # 12 - sequence (int 8), NULL for not implemented
        tmp.append(self.sequence)
        # 13 - physical port (int 8)
        tmp.append(0x00)
        # 14 - universe, (2 x 8 low byte first)
        # as specified in Artnet 4 (remember to set the value manually after):
        # Bit 3  - 0 = Universe (1-16)
        # Bit 7  - 4 = Subnet (1-16)
        # Bit 14 - 8 = Net (1-128)
        # Bit 15     = 0
        # this means 16 * 16 * 128 = 32768 universes per port
        # a subnet is a group of 16 Universes
        # 16 subnets will make a net, there are 128 of them
        tmp.append(subnet << 4 | universe)
        tmp.append(net & 0xFF)
        return tmp

    def __make_packetsize_byte(self, packet_size):
        # 16 - packet size (2 x 8 high byte first)
        #packet_size = put_in_range(packet_size, 2, 512, self.make_even)
        psize = bytearray()
        msb, lsb = shift_this(packet_size)		# convert to MSB / LSB
        psize.append(msb)
        psize.append(lsb)
        return psize

    def send_data(self, data: bytearray, universe: int):
        """Finally send data."""
        packet = self.header_list[universe-1] + self.__make_packetsize_byte(len(data))
        packet.extend(data)

        try:
            self.socket_client.sendto(packet, (self.target_ip, self.UDP_PORT))
        except socket.error as error:
            print(f"ERROR: Socket error with exception: {error}")
        finally:
            self.sequence = (self.sequence + 1) % 256

    def close(self):
        """Close UDP socket."""
        self.socket_client.close()

    # THREADING #

    def start(self):
        """Starts thread clock."""
        self.show()
        self.__clock = Timer((1000.0 / self.fps) / 1000.0, self.start)
        self.__clock.daemon = True
        self.__clock.start()

    def stop(self):
        """Stops thread clock."""
        if self.__clock is not None:
            self.__clock.cancel()

    # SETTERS - DATA #

    def clear(self):
        """Clear DMX buffer."""
        self.buffer = bytearray(self.packet_size)

    # AUX Function #

    def send(self, packet):
        """Set buffer and send straightaway.

        Args:
        array - integer array to send
        """
        self.set(packet)
        self.show()


class SmartNetServer():
    """(Very) simple implementation of an Artnet Server."""

    UDP_PORT = 6454
    socket_server = None
    ARTDMX_HEADER = b'Art-Net\x00\x00P\x00\x0e'
    listeners = []

    def __init__(self):
        """Initializes Art-Net server."""
        # server active flag
        self.listen = True

        self.server_thread = Thread(target=self.__init_socket, daemon=True)
        self.server_thread.start()

    def __init_socket(self):
        """Initializes server socket."""
        # Bind to UDP on the correct PORT
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_server.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_server.bind(('', self.UDP_PORT))  # Listen on any valid IP

        while self.listen:

            data, unused_address = self.socket_server.recvfrom(1024)

            # only dealing with Art-Net DMX
            if self.validate_header(data):

                # check if this address is in any registered listener
                for listener in self.listeners:

                    # is it the address we are listening to
                    if listener['address_mask'] == data[14:16]:
                        listener['buffer'] = list(data)[18:]

                        # check for registered callbacks
                        if listener['callback'] is not None:
                            listener['callback'](listener['buffer'], listener['universe'])

    def __del__(self):
        """Graceful shutdown."""
        self.listeners.clear()
        self.close()

    def __str__(self):
        """Printable object state."""
        state = "===================================\n"
        state += "Stupid Artnet Listening\n"
        return state

    def register_listener(self, universe=0, sub=0, net=0,
                          is_simplified=True, callback_function=None):
        """Adds a listener to an Art-Net Universe.

        Args:
        universe - Universe to listen
        sub - Subnet to listen
        net - Net to listen
        is_simplified - Whether to use nets and subnet or universe only,
        see User Guide page 5 (Universe Addressing)
        callback_function - Function to call when new packet is received

        Returns:
        id - id of listener, used to delete listener if required
        """
        listener_id = len(self.listeners)
        new_listener = {
            'id': listener_id,
            'simplified': is_simplified,
            'address_mask': make_address_mask(universe, sub, net, is_simplified),
            'callback': callback_function,
            'buffer': [],
            'universe': universe
        }

        self.listeners.append(new_listener)

        return listener_id

    def register_multiple_listeners(self, universes: list = [0], sub=0, net=0,
                                    is_simplified=True, callback_function=None):
        """Adds multiple listeners for multiple universes.
        Args:
        universes - List of universes to listen
        sub - Subnet to listen
        net - Net to listen
        is_simplified - Whether to use nets and subnet or universe only,
        see User Guide page 5 (Universe Addressing)
        callback_function - Function to call when new packet is received
        Returns:
        listener_list - list of all used listener ids, used to delete listener if required
        """
        listener_list = []
        for universe in universes:
            listener_list.append(self.register_listener(universe, sub, net, is_simplified, callback_function))
        return listener_list
    
    def delete_listener(self, listener_id):
        """Deletes a registered listener.

        Args:
        listener_id - Id of listener to delete

        Returns:
        None
        """
        self.listeners = [
            i for i in self.listeners if not i['id'] == listener_id]

    def delete_all_listener(self):
        """Deletes all registered listeners.

        Returns:
        None
        """
        self.listeners = []

    def see_buffer(self, listener_id):
        """Show buffer values."""
        for listener in self.listeners:
            if listener.get('id') == listener_id:
                return listener.get('buffer')

        return "Listener not found"

    def get_buffer(self, listener_id):
        """Return buffer values."""
        for listener in self.listeners:
            if listener.get('id') == listener_id:
                return listener.get('buffer')
        print("Buffer object not found")
        return []

        print("No Listener with given id found")
        return []

    def clear_buffer(self, listener_id):
        """Clear buffer in listener."""
        for listener in self.listeners:
            if listener.get('id') == listener_id:
                listener['buffer'] = []

    def set_callback(self, listener_id, callback_function):
        """Add / change callback to a given listener."""
        for listener in self.listeners:
            if listener.get('id') == listener_id:
                listener['callback'] = callback_function

    def set_address_filter(self, listener_id, universe, sub=0, net=0,
                           is_simplified=True):
        """Add / change filter to existing listener."""
        # make mask bytes
        address_mask = make_address_mask(
            universe, sub, net, is_simplified)

        # find listener
        for listener in self.listeners:
            if listener.get('id') == listener_id:
                listener['simplified'] = is_simplified
                listener['address_mask'] = address_mask
                listener['buffer'] = []

    def close(self):
        """Close UDP socket."""
        self.listen = False         # Set flag
        self.server_thread.join()              # Terminate thread once jobs are complete

    @staticmethod
    def validate_header(header):
        """Validates packet header as Art-Net packet.

        - The packet header spells Art-Net
        - The definition is for DMX Artnet (OPCode 0x50)
        - The protocol version is 15

        Args:
        header - Packet header as bytearray

        Returns:
        boolean - comparison value

        """
        return header[:12] == SmartNetServer.ARTDMX_HEADER