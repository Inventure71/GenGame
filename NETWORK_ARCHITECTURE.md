# Network Architecture - UDP Binary Protocol

## Overview

The game uses a hybrid TCP/UDP networking architecture with binary serialization for maximum performance and minimal latency.

## Architecture Summary

### Protocols
- **TCP**: Connection management, handshakes, and reliable events (player join/leave, game over)
- **UDP**: High-frequency game data (inputs, world state)
- **Binary Format**: Python `struct` module for compact serialization

### Tick Rates
- **Server**: 60Hz simulation, 30Hz state broadcast
- **Client**: 30Hz input send, 60Hz rendering with interpolation

## Network Flow

```
┌─────────────┐                    ┌─────────────┐
│   Client    │                    │   Server    │
│             │                    │             │
│  Render     │◄────UDP State─────┤  Simulate   │
│   60Hz      │     (30Hz)         │    60Hz     │
│             │                    │             │
│  Input      │─────UDP Input─────►│  Process    │
│   30Hz      │     (30Hz)         │   Inputs    │
│             │                    │             │
│  TCP Events │◄────TCP Events────►│  TCP Events │
│  (Reliable) │   (Join/Leave)     │  (Reliable) │
└─────────────┘                    └─────────────┘
```

## Bandwidth Optimization

### Packet Sizes (Binary)
- **Input**: 13 bytes (flags + mouse position)
- **Character State**: 18 bytes (position, health, weapon, flags)
- **Projectile State**: 16 bytes (position, direction, type)
- **Full State** (2 players, 10 projectiles): ~225 bytes

### Bandwidth Comparison
| Metric | Old (JSON 60Hz) | New (Binary 30Hz) | Reduction |
|--------|-----------------|-------------------|-----------|
| State Packet | ~1400 bytes | 225 bytes | 84% |
| Bandwidth | ~82 KB/s | ~6.6 KB/s | **92%** |
| Input | Variable | 0.38 KB/s | - |

## Key Design Decisions

### 1. Server: 60Hz Simulation, 30Hz Broadcast
- **Why**: Maintains smooth physics while reducing bandwidth by 50%
- **How**: Server ticks every frame but only broadcasts state every other frame
- **Result**: Responsive gameplay without network bottleneck

### 2. Client: 30Hz Input Send
- **Why**: Movement/aiming doesn't need 60Hz precision over network
- **How**: Client sends input every other frame (server uses last known input if packet lost)
- **Result**: 50% less upstream bandwidth with no perceivable lag

### 3. Binary Serialization
- **Why**: JSON is verbose and slow to parse
- **How**: Python `struct` module with fixed-size packets
- **Result**: 84% smaller packets, faster serialization

### 4. Gap Filling (Last Known Input)
- **Why**: UDP packets can be lost or arrive out of order
- **How**: Server keeps last received input per client, uses it when no new packet arrives
- **Result**: Smooth movement even with 10-20% packet loss

### 5. Client-Side Prediction
- **Why**: Local player feels laggy if waiting for server
- **How**: Client applies input immediately, server corrects only if drift > 15px
- **Result**: Instant feedback for local player, server stays authoritative

## File Structure

```
BASE_components/
├── network_protocol.py    # Binary packet definitions
├── BASE_network.py        # TCP/UDP socket management
└── BASE_arena.py          # Core networking logic

GameFolder/
└── arenas/
    └── GAME_arena.py      # Game-specific networking overrides
```

## Protocol Details

### Input Packet (13 bytes)
```
[Type:1][PlayerID:1][Seq:2][Flags:1][MouseX:4][MouseY:4]
```

**Flags (bitmask)**:
- `0x01`: Left
- `0x02`: Right
- `0x04`: Up
- `0x08`: Down
- `0x10`: Mouse Left Click
- `0x20`: Mouse Right Click
- `0x40`: Drop (Q)
- `0x80`: Special (E/F)

### Character State (18 bytes)
```
[PlayerID:1][X:4][Y:4][VelY:4][Health:2][Lives:1][Flags:1][WeaponID:1]
```

**Flags (bitmask)**:
- `0x01`: Alive
- `0x02`: Eliminated
- `0x04`: On Ground
- `0x08`: Flying

### State Packet (Variable)
```
[Header:11][Characters:N*18][Projectiles:M*16][Weapons:K*9]
```

**Header**:
```
[Type:1][Seq:2][Tick:4][NumChars:1][NumProj:1][NumWeapons:1][GameFlags:1]
```

## Performance Benefits

### Latency Reduction
- **Binary Parsing**: ~10x faster than JSON
- **UDP**: No TCP head-of-line blocking
- **30Hz Client Input**: Reduces processing overhead

### Bandwidth Reduction
- **Compact Format**: 84% smaller than JSON
- **30Hz State**: 50% less broadcast traffic
- **Gap Filling**: No retransmission overhead

### Scalability
- **Per-Client**: ~7 KB/s downstream, 0.4 KB/s upstream
- **4 Players**: ~28 KB/s server bandwidth
- **8 Players**: ~56 KB/s server bandwidth

## Testing

Run the game:
```bash
# Terminal 1 (Server)
python main.py server

# Terminal 2 (Client)
python main.py client
```

Expected behavior:
- Server runs at 60 FPS with smooth physics
- Client receives updates at 30Hz but renders at 60 FPS
- Input latency < 50ms on localhost
- Smooth interpolation between server states

