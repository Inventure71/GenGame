"""
Hybrid TCP/UDP Network Layer for GenGame

- TCP: Connection management, reliable events (join/leave, game over)
- UDP: High-frequency game data (inputs at 60Hz, state at 30Hz)
"""

import socket
import select
import time
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass

from BASE_components.network_protocol import (
    pack_input, unpack_input, pack_state, unpack_state,
    pack_event, unpack_event, get_packet_type,
    InputPacket, StatePacket, EventType,
    PACKET_INPUT, PACKET_STATE
)

@dataclass
class ClientInfo:
    """Information about a connected client (Server-side)."""
    client_id: int
    name: str
    tcp_socket: socket.socket
    udp_addr: Optional[Tuple[str, int]] = None
    last_input_seq: int = 0
    last_input_time: float = 0.0
    last_input: Optional[InputPacket] = None

class BaseNetwork:
    """
    Hybrid TCP/UDP networking.
    Handles socket management and packet IO.
    """
    
    def __init__(self, address: str = "localhost", port: int = 5555):
        self.server_addr = (address, port)
        self.udp_port = port + 1
        
        # Sockets
        self.tcp_sock: Optional[socket.socket] = None # Server: Listener, Client: Connection
        self.udp_sock: Optional[socket.socket] = None
        
        # State
        self.clients: Dict[int, ClientInfo] = {} # Server only
        self.next_client_id = 1
        self.my_client_id = 0
        self.is_connected = False
        self.server_udp_target: Optional[Tuple[str, int]] = None # Client only
        
        # Sequence tracking
        self.input_sequence = 0
        self.received_states: List[Tuple[int, StatePacket]] = [] 
        self.max_state_buffer = 10
        self.last_input_send_time = 0.0  # Client side input throttle
        
        # Callbacks
        self.on_client_join: Optional[Callable] = None
        self.on_client_leave: Optional[Callable] = None

    def _create_socket(self, proto: int, bind_addr: Tuple[str, int] = None) -> socket.socket:
        sock = socket.socket(socket.AF_INET, proto)
        if proto == socket.SOCK_STREAM:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        if bind_addr:
            try:
                sock.bind(bind_addr)
            except OSError as e:
                print(f"Network Error: Could not bind to {bind_addr}. {e}")
                raise
        return sock

    # =========================================================================
    # SERVER
    # =========================================================================
    
    def start_server(self, address: Tuple[str, int] = None):
        if address:
            self.server_addr = address
            self.udp_port = address[1] + 1
            
        self.tcp_sock = self._create_socket(socket.SOCK_STREAM, self.server_addr)
        self.tcp_sock.listen(8)
        
        self.udp_sock = self._create_socket(socket.SOCK_DGRAM, (self.server_addr[0], self.udp_port))
        
        print(f"[Server] Listening TCP: {self.server_addr}, UDP: {self.udp_port}")

    def accept_new_clients(self) -> List[int]:
        if not self.tcp_sock: return []
        new_ids = []
        
        # 1. Accept new connections
        try:
            readable, _, _ = select.select([self.tcp_sock], [], [], 0)
            for sock in readable:
                client_sock, addr = sock.accept()
                client_sock.setblocking(False)
                
                cid = self.next_client_id
                self.next_client_id += 1
                
                self.clients[cid] = ClientInfo(cid, f"Player{cid}", client_sock)
                
                # Send Handshake
                try:
                    client_sock.sendall(pack_event(EventType.HANDSHAKE_ACK, bytes([cid])))
                except:
                    pass
                
                print(f"[Server] Client {cid} connected from {addr}")
                new_ids.append(cid)
                if self.on_client_join: self.on_client_join(cid, f"Player{cid}")
        except (socket.error, BlockingIOError):
            pass
            
        # 2. Check existing clients for data/disconnects
        if self.clients:
            try:
                client_sockets = [c.tcp_socket for c in self.clients.values()]
                readable, _, _ = select.select(client_sockets, [], [], 0)
                
                dead_ids = []
                for sock in readable:
                    try:
                        data = sock.recv(1024)
                        if not data:
                            # EOF = Disconnected
                            cid = next((cid for cid, c in self.clients.items() if c.tcp_socket == sock), None)
                            if cid: dead_ids.append(cid)
                        # Else: data received (ignored for now, or could be events)
                    except (socket.error, ConnectionResetError):
                        cid = next((cid for cid, c in self.clients.items() if c.tcp_socket == sock), None)
                        if cid: dead_ids.append(cid)
                
                for cid in dead_ids:
                    self.disconnect_client(cid)
            except:
                pass

        return new_ids

    def receive_client_inputs(self) -> Dict[int, InputPacket]:
        inputs = {}
        if not self.udp_sock: return inputs
        
        while True:
            try:
                data, addr = self.udp_sock.recvfrom(64)
                if get_packet_type(data) != PACKET_INPUT: continue
                
                packet = unpack_input(data)
                if not packet: continue
                
                cid = packet.player_id
                if cid in self.clients:
                    client = self.clients[cid]
                    if not client.udp_addr:
                        client.udp_addr = addr # Bind UDP address
                    
                    # Sequence check (simple wrapping handling)
                    diff = (packet.sequence - client.last_input_seq) % 65536
                    if diff < 32768: 
                        client.last_input_seq = packet.sequence
                        client.last_input_time = time.time()
                        client.last_input = packet
                        inputs[cid] = packet
            except BlockingIOError:
                break
            except socket.error:
                break
        
        # Gap filling
        now = time.time()
        for cid, client in self.clients.items():
            if cid not in inputs and client.last_input and (now - client.last_input_time < 0.2):
                inputs[cid] = client.last_input
                
        return inputs

    def broadcast_state_udp(self, state: StatePacket):
        if not self.udp_sock: return
        data = pack_state(state)
        for client in self.clients.values():
            if client.udp_addr:
                try:
                    self.udp_sock.sendto(data, client.udp_addr)
                except socket.error:
                    pass

    def broadcast_event_tcp(self, event_type: EventType, payload: bytes = b''):
        data = pack_event(event_type, payload)
        self._send_to_all_tcp(data)

    def _send_to_all_tcp(self, data: bytes):
        dead_clients = []
        for cid, client in self.clients.items():
            try:
                client.tcp_socket.sendall(data)
            except (socket.error, BrokenPipeError):
                dead_clients.append(cid)
        for cid in dead_clients:
            self.disconnect_client(cid)

    def disconnect_client(self, cid: int):
        if cid in self.clients:
            print(f"[Server] Disconnecting Client {cid}")
            try: self.clients[cid].tcp_socket.close()
            except: pass
            del self.clients[cid]
            if self.on_client_leave: self.on_client_leave(cid)

    # =========================================================================
    # CLIENT
    # =========================================================================

    def connect_to_server(self, address: Tuple[str, int] = None):
        if address:
            self.server_addr = address
            self.udp_port = address[1] + 1
            
        self.tcp_sock = self._create_socket(socket.SOCK_STREAM)
        
        # Handle non-blocking connect
        try:
            self.tcp_sock.connect(self.server_addr)
        except (BlockingIOError, socket.error) as e:
            # EINPROGRESS (36 on Mac/Linux, 10035 on Win) is expected for non-blocking connect
            if e.errno not in (36, 115, 10035): 
                raise e
            
            # Wait for connection to complete
            _, writable, _ = select.select([], [self.tcp_sock], [], 5.0)
            if not writable:
                raise ConnectionError("Connection timed out")
            
            # Check for errors after select
            err = self.tcp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err != 0:
                raise ConnectionError(f"Connection failed: {err}")
        
        # UDP socket binds to random port
        self.udp_sock = self._create_socket(socket.SOCK_DGRAM, ('', 0))
        self.server_udp_target = (self.server_addr[0], self.udp_port)
        
        print(f"[Client] Connected to {self.server_addr}")
        self._wait_for_handshake()

    def _wait_for_handshake(self):
        start = time.time()
        while time.time() - start < 5.0:
            try:
                readable, _, _ = select.select([self.tcp_sock], [], [], 0.1)
                if readable:
                    data = self.tcp_sock.recv(64)
                    if data:
                        try:
                            event = unpack_event(data)
                            if event and event[0] == EventType.HANDSHAKE_ACK:
                                if len(event[1]) > 0:
                                    self.my_client_id = int(event[1][0])
                                    self.is_connected = True
                                    print(f"[Client] ID Assigned: {self.my_client_id}")
                                    return
                                else:
                                    print("[Client] Received empty handshake payload")
                        except Exception as e:
                            print(f"[Client] Handshake unpack error: {e}")
            except (socket.error, BlockingIOError):
                pass
        raise ConnectionError("Handshake timed out")

    def send_input_udp(self, packet: InputPacket):
        if not self.udp_sock or not self.server_udp_target: return
        
        packet.sequence = self.input_sequence
        self.input_sequence = (self.input_sequence + 1) % 65536
        packet.player_id = self.my_client_id
        
        try:
            self.udp_sock.sendto(pack_input(packet), self.server_udp_target)
        except socket.error:
            pass

    def receive_state_udp(self) -> Optional[StatePacket]:
        if not self.udp_sock: return None
        
        latest = None
        while True:
            try:
                data, _ = self.udp_sock.recvfrom(2048)
                if get_packet_type(data) != PACKET_STATE: continue
                
                packet = unpack_state(data)
                if not packet: continue
                
                if latest is None: latest = packet
                else:
                    # Simple seq check
                    diff = (packet.sequence - latest.sequence) % 65536
                    if diff < 32768: latest = packet
            except BlockingIOError:
                break
            except socket.error:
                break
        return latest

    def receive_tcp_event(self) -> Optional[Tuple[EventType, bytes]]:
        if not self.tcp_sock: return None
        try:
            readable, _, _ = select.select([self.tcp_sock], [], [], 0)
            if readable:
                data = self.tcp_sock.recv(1024)
                if not data:
                    print("[Client] Server disconnected")
                    self.is_connected = False
                    return None
                return unpack_event(data)
        except (socket.error, BlockingIOError):
            pass
        return None

    def cleanup(self):
        if self.tcp_sock: self.tcp_sock.close()
        if self.udp_sock: self.udp_sock.close()
        for c in self.clients.values():
            try: c.tcp_socket.close()
            except: pass
        self.clients.clear()
