import socket
import base64
import hashlib
import platform
import os
import json
import sys
import importlib
import traceback
import types

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
SECRET_OFFSET = 717171 
REMOTE_DOMAIN = "gengame.inventure71.duckdns.org"

def base_encode(n: int) -> str:
    if n == 0: return ALPHABET[0]
    arr = []
    while n:
        n, rem = divmod(n, len(ALPHABET))
        arr.append(ALPHABET[rem])
    arr.reverse()
    return ''.join(arr)

def base_decode(code: str) -> int:
    n = 0
    for char in code:
        n = n * len(ALPHABET) + ALPHABET.index(char)
    return n

def get_local_ip():
    """Gets the full local IP address (e.g., '192.168.0.1')"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except:
        return "127.0.0.1"
    finally:
        s.close()

def get_local_ip_prefix():
    """Gets the first two parts of the local IP (e.g., '192.168.')"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        # returns '192.168.'
        return '.'.join(ip.split('.')[:2]) + '.'
    except:
        return "192.168."
    finally:
        s.close()

def encrypt_code(ip: str, port: int, mode: str) -> str:
    if mode == "REMOTE":
        # Remote only needs to hide the port
        val = port + SECRET_OFFSET
        return "R" + base_encode(val)
    else:
        # LAN: Split IP '192.168.3.45' -> ['192', '168', '3', '45']
        parts = ip.split('.')
        subnet = int(parts[2])  # The '3'
        last = int(parts[3])    # The '45'
        
        # Pack: [Port (16b)][Subnet (8b)][Last (8b)]
        packed = (port << 16) | (subnet << 8) | last
        return "L" + base_encode(packed + SECRET_OFFSET)

def decrypt_code(code: str):
    code = code.upper().strip()
    prefix = code[0]
    payload = code[1:]
    
    val = base_decode(payload) - SECRET_OFFSET
    
    if prefix == "R":
        return REMOTE_DOMAIN, val
    
    elif prefix == "L":
        # Unpack the bits
        last = val & 0xFF
        subnet = (val >> 8) & 0xFF
        port = val >> 16
        
        # Reconstruct IP: '192.168.' + '3' + '.' + '45'
        full_ip = get_local_ip_prefix() + str(subnet) + "." + str(last)
        return full_ip, port
    
    return None, None

def _get_encryption_key():
    """Generate a consistent encryption key based on system information."""
    system_info = platform.system() + platform.node() + str(os.getuid())
    return hashlib.sha256(system_info.encode()).digest()[:16]  # 16 bytes for XOR key

def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for secure storage."""
    if not api_key:
        return ""

    key = _get_encryption_key()
    # XOR encryption
    encrypted = bytearray()
    key_len = len(key)
    api_bytes = api_key.encode('utf-8')

    for i, byte in enumerate(api_bytes):
        encrypted.append(byte ^ key[i % key_len])

    # Base64 encode for safe storage
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from secure storage."""
    if not encrypted_key:
        return ""

    try:
        key = _get_encryption_key()
        # Base64 decode
        encrypted = base64.b64decode(encrypted_key)
        key_len = len(key)

        # XOR decryption (same as encryption)
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key[i % key_len])

        return decrypted.decode('utf-8')
    except Exception:
        # If decryption fails, return empty string
        return ""

def reload_game_code() -> types.ModuleType:
    print("🔄 Performing deep reload of game code...")
    
    # 1. Identify all loaded GameFolder modules
    game_modules = [
        (name, module) for name, module in sys.modules.items() 
        if name.startswith('GameFolder') and module is not None
    ]
    
    # DEBUG: Check initial state of Character class in setup if loaded
    if 'GameFolder.setup' in sys.modules:
        try:
             import GameFolder.setup
             if hasattr(GameFolder.setup, 'Character'):
                 print(f"DEBUG: Before reload, GameFolder.setup.Character ID: {id(GameFolder.setup.Character)}")
        except: pass

    # 2. Reload all dependencies first
    for name, module in game_modules:
        if name == 'GameFolder.setup':
            continue
        try:
            importlib.reload(module)
        except Exception as e:
            # CRITICAL FIX: Print the error so you know the patch failed!
            print(f"[error] Failed to reload {name}: {e}")
            traceback.print_exc() 
            
    # 3. Explicitly reload the entry point (setup.py) last
    # STRATEGY CHANGE: Use del + import to force fresh namespace population from reloaded dependencies
    try:
        if 'GameFolder.setup' in sys.modules:
            print("Force-clearing GameFolder.setup from sys.modules to ensure clean import...")
            del sys.modules['GameFolder.setup']
            
        import GameFolder.setup
        
        # Verify the class ID
        if hasattr(GameFolder.setup, 'Character'):
             print(f"DEBUG: After reload, GameFolder.setup.Character ID: {id(GameFolder.setup.Character)}")
        
        print("[success] Game code deep reload complete.")
        return sys.modules['GameFolder.setup']
    except Exception as e:
        print(f"[error] CRITICAL: Failed to reload setup.py: {e}")
        traceback.print_exc()
        return None

def load_settings() -> dict:
    """Load settings from config file."""
    config_path = os.path.join("__config", "settings.json")
    if os.path.exists(config_path):
        dictionary = {}
        try:
            with open(config_path, 'r') as f:
                settings = json.load(f)

            dictionary["success"] = True
            dictionary["username"] = settings.get("username", "")
            dictionary["gemini_api_key"] = decrypt_api_key(settings.get("gemini_api_key", ""))
            dictionary["openai_api_key"] = decrypt_api_key(settings.get("openai_api_key", ""))
            dictionary["selected_provider"] = settings.get("selected_provider", "GEMINI")
            dictionary["model_name"] = settings.get("model", "models/gemini-3-flash-preview")
            dictionary["base_working_backup"] = settings.get("base_working_backup", None)
            
            return dictionary
        
        except Exception as e:
            print(f"Failed to load settings: {e}")
            dictionary["success"] = False
            return dictionary
    else:
        dictionary["success"] = False
        return dictionary