"""
Network Protocol for GenGame - Binary Serialization (Simplified)

Packet Types:
- INPUT (0x01): Client -> Server, player inputs
- STATE (0x02): Server -> Client, world state snapshot
- EVENT (0x03): Bidirectional via TCP, reliable events
"""

import struct
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import IntEnum

# =============================================================================
# CONSTANTS
# =============================================================================

PACKET_INPUT = 0x01
PACKET_STATE = 0x02
PACKET_EVENT = 0x03

MAX_PLAYERS = 8
MAX_PROJECTILES = 64
MAX_WEAPONS = 16

# Input flags
INPUT_LEFT = 0x01
INPUT_RIGHT = 0x02
INPUT_UP = 0x04
INPUT_DOWN = 0x08
INPUT_MOUSE_L = 0x10
INPUT_MOUSE_R = 0x20
INPUT_DROP = 0x40
INPUT_SPECIAL = 0x80

class EventType(IntEnum):
    PLAYER_JOIN = 1
    PLAYER_LEAVE = 2
    GAME_START = 3
    GAME_OVER = 4
    CHAT = 5
    HANDSHAKE = 6
    HANDSHAKE_ACK = 7

# =============================================================================
# PACKET CLASSES
# =============================================================================

@dataclass
class InputPacket:
    player_id: int
    sequence: int
    input_flags: int
    mouse_x: float
    mouse_y: float
    
    # Static size of payload (excluding packet type header)
    SIZE = 12
    
    def pack(self) -> bytes:
        return struct.pack('<BHBff', self.player_id, self.sequence % 65536, 
                         self.input_flags, self.mouse_x, self.mouse_y)

    @classmethod
    def unpack(cls, data: bytes) -> Optional['InputPacket']:
        if len(data) < cls.SIZE: return None
        try:
            pid, seq, flags, mx, my = struct.unpack('<BHBff', data[:cls.SIZE])
            return cls(pid, seq, flags, mx, my)
        except struct.error:
            return None

@dataclass
class CharacterState:
    player_id: int
    x: float
    y: float
    vel_y: float
    health: float
    lives: int
    flags: int
    weapon_id: int
    
    SIZE = 18 # 1+4+4+4+2+1+1+1
    
    def pack(self) -> bytes:
        health_fixed = int(min(self.health, 999.9) * 10)
        return struct.pack('<BfffHBBB', self.player_id, self.x, self.y, self.vel_y, 
                         health_fixed, self.lives, self.flags, self.weapon_id)
                         
    @classmethod
    def unpack(cls, data: bytes) -> Optional['CharacterState']:
        if len(data) < cls.SIZE: return None
        try:
            pid, x, y, vy, h_fixed, lives, flags, wid = struct.unpack('<BfffHBBB', data[:cls.SIZE])
            return cls(pid, x, y, vy, h_fixed / 10.0, lives, flags, wid)
        except struct.error:
            return None

@dataclass
class ProjectileState:
    proj_id: int
    proj_type: int
    x: float
    y: float
    dir_x: float
    dir_y: float
    owner_id: int
    meta: int
    
    SIZE = 17 # 2+1+4+4+2+2+1+1
    
    def pack(self) -> bytes:
        dx = int(max(-1.0, min(1.0, self.dir_x)) * 32767)
        dy = int(max(-1.0, min(1.0, self.dir_y)) * 32767)
        return struct.pack('<HBffhhBB', self.proj_id, self.proj_type, self.x, self.y, 
                         dx, dy, self.owner_id, self.meta)
                         
    @classmethod
    def unpack(cls, data: bytes) -> Optional['ProjectileState']:
        if len(data) < cls.SIZE: return None
        try:
            pid, ptype, x, y, dx, dy, oid, meta = struct.unpack('<HBffhhBB', data[:cls.SIZE])
            return cls(pid, ptype, x, y, dx / 32767.0, dy / 32767.0, oid, meta)
        except struct.error:
            return None

@dataclass 
class WeaponPickupState:
    weapon_type: int
    x: float
    y: float
    
    SIZE = 9 # 1+4+4
    
    def pack(self) -> bytes:
        return struct.pack('<Bff', self.weapon_type, self.x, self.y)
        
    @classmethod
    def unpack(cls, data: bytes) -> Optional['WeaponPickupState']:
        if len(data) < cls.SIZE: return None
        try:
            wt, x, y = struct.unpack('<Bff', data[:cls.SIZE])
            return cls(wt, x, y)
        except struct.error:
            return None

@dataclass
class StatePacket:
    sequence: int
    server_tick: int
    num_characters: int
    num_projectiles: int
    num_weapons: int
    game_flags: int
    characters: List[CharacterState]
    projectiles: List[ProjectileState]
    weapons: List[WeaponPickupState]
    
    HEADER_SIZE = 11 # 1(type) + 2 + 4 + 1 + 1 + 1 + 1
    
    # Note: Logic moved to pack_state function to handle composition

# =============================================================================
# PUBLIC API (Facade)
# =============================================================================

def pack_input(packet: InputPacket) -> bytes:
    return struct.pack('<B', PACKET_INPUT) + packet.pack()

def unpack_input(data: bytes) -> Optional[InputPacket]:
    if len(data) < InputPacket.SIZE + 1: return None # +1 for type
    # We strip the first byte (type) manually here assuming caller passed full packet
    return InputPacket.unpack(data[1:])

def pack_state(packet: StatePacket) -> bytes:
    # Header: Type + Seq + Tick + Counts + Flags
    header = struct.pack('<BHIBBBB', PACKET_STATE, packet.sequence % 65536, packet.server_tick,
                        len(packet.characters), len(packet.projectiles), len(packet.weapons),
                        packet.game_flags)
    
    payload = bytearray(header)
    for c in packet.characters[:MAX_PLAYERS]: payload.extend(c.pack())
    for p in packet.projectiles[:MAX_PROJECTILES]: payload.extend(p.pack())
    for w in packet.weapons[:MAX_WEAPONS]: payload.extend(w.pack())
    
    return bytes(payload)

def unpack_state(data: bytes) -> Optional[StatePacket]:
    if len(data) < StatePacket.HEADER_SIZE: return None
    try:
        ptype, seq, tick, n_char, n_proj, n_weap, flags = struct.unpack('<BHIBBBB', data[:StatePacket.HEADER_SIZE])
        if ptype != PACKET_STATE: return None
        
        offset = StatePacket.HEADER_SIZE
        chars = []
        for _ in range(min(n_char, MAX_PLAYERS)):
            c = CharacterState.unpack(data[offset:])
            if c: chars.append(c); offset += CharacterState.SIZE
            
        projs = []
        for _ in range(min(n_proj, MAX_PROJECTILES)):
            p = ProjectileState.unpack(data[offset:])
            if p: projs.append(p); offset += ProjectileState.SIZE
            
        weaps = []
        for _ in range(min(n_weap, MAX_WEAPONS)):
            w = WeaponPickupState.unpack(data[offset:])
            if w: weaps.append(w); offset += WeaponPickupState.SIZE
            
        return StatePacket(seq, tick, n_char, n_proj, n_weap, flags, chars, projs, weaps)
    except struct.error:
        return None

def pack_event(event_type: EventType, payload: bytes = b'') -> bytes:
    return struct.pack('<BBH', PACKET_EVENT, event_type, len(payload)) + payload

def unpack_event(data: bytes) -> Optional[Tuple[EventType, bytes]]:
    if len(data) < 4: return None
    try:
        ptype, et, length = struct.unpack('<BBH', data[:4])
        if ptype != PACKET_EVENT: return None
        return (EventType(et), data[4:4+length])
    except (struct.error, ValueError):
        return None

def get_packet_type(data: bytes) -> Optional[int]:
    return data[0] if data else None

# =============================================================================
# HELPER FUNCTIONS (Flags)
# =============================================================================

def input_flags_from_keys(keys: List) -> int:
    flags = 0
    # Map key names to flags
    # (Simplified for readability)
    mapping = {
        'left': INPUT_LEFT, 'a': INPUT_LEFT,
        'right': INPUT_RIGHT, 'd': INPUT_RIGHT,
        'up': INPUT_UP, 'w': INPUT_UP, 'space': INPUT_UP,
        'down': INPUT_DOWN, 's': INPUT_DOWN,
        'q': INPUT_DROP,
        'e': INPUT_SPECIAL, 'f': INPUT_SPECIAL
    }
    
    for k in keys:
        name = k[0] if isinstance(k, list) else k
        if name in mapping: flags |= mapping[name]
        if name == 'M_1':
            if len(k) >= 3 and k[2]: flags |= INPUT_MOUSE_L
            if len(k) >= 5 and k[4]: flags |= INPUT_MOUSE_R
    return flags

def keys_from_input_flags(flags: int, mouse_pos: Tuple[float, float]) -> List:
    keys = []
    if flags & INPUT_LEFT: keys.append(['left'])
    if flags & INPUT_RIGHT: keys.append(['right'])
    if flags & INPUT_UP: keys.append(['up'])
    if flags & INPUT_DOWN: keys.append(['down'])
    if flags & INPUT_DROP: keys.append(['q'])
    if flags & INPUT_SPECIAL: keys.append(['e'])
    
    l_click = bool(flags & INPUT_MOUSE_L)
    r_click = bool(flags & INPUT_MOUSE_R)
    keys.append(['M_1', list(mouse_pos), l_click, False, r_click])
    return keys

# Character flags
CHAR_ALIVE = 0x01
CHAR_ELIMINATED = 0x02
CHAR_ON_GROUND = 0x04
CHAR_FLYING = 0x08

def char_flags_pack(is_alive: bool, is_eliminated: bool, on_ground: bool, is_flying: bool = False) -> int:
    flags = 0
    if is_alive: flags |= CHAR_ALIVE
    if is_eliminated: flags |= CHAR_ELIMINATED
    if on_ground: flags |= CHAR_ON_GROUND
    if is_flying: flags |= CHAR_FLYING
    return flags

def char_flags_unpack(flags: int) -> Tuple[bool, bool, bool, bool]:
    return (bool(flags & CHAR_ALIVE), bool(flags & CHAR_ELIMINATED), 
            bool(flags & CHAR_ON_GROUND), bool(flags & CHAR_FLYING))

# Game state flags
GAME_OVER = 0x01
GAME_PAUSED = 0x02

def game_flags_pack(game_over: bool, paused: bool = False) -> int:
    return (GAME_OVER if game_over else 0) | (GAME_PAUSED if paused else 0)

def game_flags_unpack(flags: int) -> Tuple[bool, bool]:
    return (bool(flags & GAME_OVER), bool(flags & GAME_PAUSED))
