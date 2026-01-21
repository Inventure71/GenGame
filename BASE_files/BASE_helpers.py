import socket
import base64
import hashlib
import platform
import os
import json
import sys
import importlib
import importlib.util
import traceback
import types
from dotenv import load_dotenv

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
SECRET_OFFSET = 717171 
# Remote play domain (CC-branded). Update DNS accordingly.
REMOTE_DOMAIN = "cc.inventure71.duckdns.org"

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
    """Gets the full local IP address (e.g., '192.168.0.1')
    
    Checks CC_PUBLIC_IP environment variable first (useful for Docker),
    then legacy GENGAME_PUBLIC_IP,
    then auto-detects host IP if running in Docker, otherwise detects local IP.
    """
    # Check for environment variable override
    public_ip = os.getenv("CC_PUBLIC_IP") or os.getenv("GENGAME_PUBLIC_IP")
    if public_ip:
        return public_ip
    
    # Detect IP via network connection
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        
        # Auto-detect host IP if in Docker (Docker network IPs: 172.17-31.x.x)
        if os.path.exists("/.dockerenv") and ip.startswith("172."):
            # Try host.docker.internal (works on Docker Desktop)
            try:
                host_ip = socket.gethostbyname("host.docker.internal")
                if host_ip and host_ip != "127.0.0.1":
                    return host_ip
            except:
                pass
        
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
            print(f"[error] Failed to reload {name}: {e}")
            traceback.print_exc() 
   
    import os
    game_folder_path = os.path.join(os.path.dirname(__file__), '..', 'GameFolder')
    if os.path.exists(game_folder_path):
        for root, dirs, files in os.walk(game_folder_path):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    rel_path = os.path.relpath(os.path.join(root, file), game_folder_path)
                    module_name = 'GameFolder.' + rel_path.replace(os.sep, '.').replace('.py', '')
                    
                    # If this module isn't loaded yet, import it
                    if module_name not in sys.modules:
                        try:
                            __import__(module_name)
                            print(f"[info] Imported new module: {module_name}")
                        except Exception as e:
                            print(f"[warning] Failed to import new module {module_name}: {e}")
            
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

def validate_gamefolder_importable():
    """
    Validate that GameFolder.setup can be imported without errors.
    Returns (is_valid, error_message)
    """
    try:
        # Use importlib to test import without polluting namespace
        spec = importlib.util.find_spec("GameFolder.setup")
        if spec is None:
            return False, "GameFolder.setup module not found"
        
        # Try to load the module
        module = importlib.util.module_from_spec(spec)
        # Add to sys.modules temporarily to handle relative imports
        sys.modules['GameFolder.setup'] = module
        spec.loader.exec_module(module)
        
        # If we get here, import succeeded
        # Clean up the test import
        if 'GameFolder.setup' in sys.modules:
            del sys.modules['GameFolder.setup']
        # Also clean up any GameFolder submodules that might have been loaded
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('GameFolder.')]
        for mod_name in modules_to_remove:
            del sys.modules[mod_name]
        
        return True, None
    except ImportError as e:
        error_msg = str(e)
        # Clean up any partially loaded modules
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('GameFolder.')]
        for mod_name in modules_to_remove:
            del sys.modules[mod_name]
        return False, f"ImportError: {error_msg}"
    except SyntaxError as e:
        error_msg = str(e)
        # Clean up any partially loaded modules
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('GameFolder.')]
        for mod_name in modules_to_remove:
            del sys.modules[mod_name]
        return False, f"SyntaxError: {error_msg}"
    except Exception as e:
        error_msg = str(e)
        # Clean up any partially loaded modules
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('GameFolder.')]
        for mod_name in modules_to_remove:
            del sys.modules[mod_name]
        return False, f"Error: {error_msg}"

def ensure_gamefolder_exists():
    """Ensure GameFolder exists with content and is importable, restoring from backup if needed."""
    game_folder = "GameFolder"
    
    # Check if GameFolder exists and has content
    if not os.path.exists(game_folder) or not os.listdir(game_folder):
        print("GameFolder is missing or empty. Attempting to restore from default backup...")
        should_restore = True
    else:
        # GameFolder exists and has content, but check if it's importable
        print("GameFolder exists and has content. Validating importability...")
        is_valid, error_msg = validate_gamefolder_importable()
        
        if not is_valid:
            print(f"GameFolder is in a broken state: {error_msg}")
            print("Attempting to restore from default backup...")
            should_restore = True
        else:
            print("GameFolder is valid and importable. No need to restore from backup.")
            return True
    
    # Restore from backup if needed
    if should_restore:
        try:
            from coding.non_callable_tools.backup_handling import BackupHandler
            handler = BackupHandler("__game_backups")

            # Get available backups and pick the most recent one
            backups = handler.list_backups()
            if not backups:
                print("ERROR: No backups available to restore from!")
                return False

            # Sort by modification time (most recent first)
            backups_with_mtime = [(b, os.path.getmtime(os.path.join("__game_backups", b))) for b in backups]
            backups_with_mtime.sort(key=lambda x: x[1], reverse=True)
            default_backup = backups_with_mtime[0][0]

            print(f"Restoring from backup: {default_backup}")
            print(f"Target path: {game_folder}")
            handler.restore_backup(default_backup, target_path=game_folder)
            print("GameFolder restored successfully.")
            
            # Validate the restored GameFolder
            print("Validating restored GameFolder...")
            is_valid, error_msg = validate_gamefolder_importable()
            if not is_valid:
                print(f"WARNING: Restored GameFolder is still broken: {error_msg}")
                print("You may need to manually fix the issue or restore from a different backup.")
                return False
            
            print("Restored GameFolder is valid and importable.")
            return True

        except Exception as e:
            print(f"ERROR: Failed to restore GameFolder from backup: {e}")
            return False
    
    return True

def load_settings(auto_create_settings: bool = True) -> dict:
    """Load settings from config file."""
    load_dotenv()
    config_path = os.path.join("__config", "settings.json")
    dictionary = {}
    settings = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                settings = json.load(f)
                dictionary["success"] = True
        
        except Exception as e:
            print(f"Failed to load settings: {e}")
            dictionary["success"] = False

    else:
        dictionary["success"] = False
    
    dictionary["username"] = settings.get("username", "")
    dictionary["gemini_api_key"] = decrypt_api_key(settings.get("gemini_api_key", ""))
    if dictionary["gemini_api_key"] == "":
        print("WARNING: No Gemini API key found in settings, trying to use environment variable GEMINI_API_KEY_PAID")
        dictionary["gemini_api_key"] = os.getenv("GEMINI_API_KEY_PAID") or ""
    dictionary["openai_api_key"] = decrypt_api_key(settings.get("openai_api_key", ""))
    if dictionary["openai_api_key"] == "":
        print("WARNING: No OpenAI API key found in settings, trying to use environment variable OPENAI_API_KEY")
        dictionary["openai_api_key"] = os.getenv("OPENAI_API_KEY") or ""
    dictionary["selected_provider"] = settings.get("selected_provider", "GEMINI")
    dictionary["model_name"] = settings.get("model", "models/gemini-3-flash-preview")
    dictionary["base_working_backup"] = settings.get("base_working_backup", None)
    
    if auto_create_settings:
        result = create_settings_file(dictionary["username"], dictionary["gemini_api_key"], dictionary["openai_api_key"], dictionary["selected_provider"], dictionary["model_name"], dictionary["base_working_backup"], already_encrypted=False)
        if result["success"]:
            print(f"Settings file created successfully: {result['result']}")
        else:
            print(f"Failed to create settings: {result['result']}")
        dictionary["success"] = result["success"]
    
    return dictionary

def create_settings_file(username: str, gemini_api_key: str, openai_api_key: str, selected_provider: str, model_name: str, base_working_backup: str = None, already_encrypted: bool = False) -> dict:
    """Create settings.json from environment variables if it doesn't exist."""
    config_dir = "__config"
    config_path = os.path.join(config_dir, "settings.json")

    # create directory if needed
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    # create minimal settings file
    if not already_encrypted:
        gemini_api_key = encrypt_api_key(gemini_api_key)
        openai_api_key = encrypt_api_key(openai_api_key)
    
    settings = {
        "username": username,
        "gemini_api_key": gemini_api_key,
        "openai_api_key": openai_api_key,
        "selected_provider": selected_provider,
        "model": model_name,
        "base_working_backup": base_working_backup
    }

    try:
        with open(config_path, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"Created settings file at {config_path}")
        return {"success": True, "result": "Settings file created successfully"}
    except Exception as e:
        print(f"Failed to create settings: {e}")
        return {"success": False, "result": f"Failed to create settings: {e}"}