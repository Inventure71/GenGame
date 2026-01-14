import glob
import os
import shutil

def open_file(file_path: str) -> str | None:
    """
    Safely opens a text file and returns its content.
    Returns None for binary files, missing files, or other errors.
    Returns empty string for empty text files.
    Includes fallback to original project directory for coding/ files.
    """
    return _open_file_with_fallback(file_path)

def _open_file_with_fallback(file_path: str) -> str | None:
    """
    Open file with fallback to original project directory for prompts/system files.
    """
    # First try the current working directory (.gengame)
    if os.path.exists(file_path):
        try:
            # Check file size first
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return ""  # Empty file

            # Check if file is binary by reading first few bytes
            with open(file_path, 'rb') as f:
                sample = f.read(min(1024, file_size))  # Read first 1KB or file size

            # Check for null bytes or high ratio of non-ASCII characters
            if b'\x00' in sample:
                return None  # Binary file

            # Count non-ASCII characters
            non_ascii_count = sum(1 for byte in sample if byte > 127)
            if len(sample) > 0 and (non_ascii_count / len(sample)) > 0.3:
                # More than 30% non-ASCII characters - likely binary
                return None

            # Try to decode as UTF-8 (allow partial sequences)
            try:
                sample.decode('utf-8')
            except UnicodeDecodeError:
                # If decoding fails, it might be due to cutting off a multi-byte sequence
                # Try with errors='replace' to see if it's still mostly valid text
                sample.decode('utf-8', errors='replace')

            # If we get here, it's likely text - read the full file
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return content

        except (UnicodeDecodeError, OSError, IOError, PermissionError):
            pass

    # File not found in current directory, try original project directory
    # This is for prompts and system files that aren't copied to .gengame
    if file_path.startswith('coding/'):
        try:
            # Get the original project directory
            # We can find it by going up from the current script location
            current_file = __file__  # This helpers.py file
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

            if 'GenGame' in project_root and not project_root.endswith('.gengame'):
                original_path = os.path.join(project_root, file_path)
                if os.path.exists(original_path):
                    # Recursively call with the original path
                    return _open_file_with_fallback(original_path)
        except:
            pass

    # File is binary, corrupted, or inaccessible
    return None

def load_prompt(prompt_file: str, include_general_context: bool = True) -> str:
    prompt = open_file(prompt_file)
    if prompt is None:
        raise FileNotFoundError(f"Prompt file {prompt_file} not found, from {os.getcwd()}")

    # Handle {include:path} directives
    import re
    include_pattern = r'\{include:([^}]+)\}'
    def replace_include(match):
        include_path = match.group(1)
        full_path = f"coding/system_prompts/{include_path}"
        included_content = open_file(full_path)
        if included_content is None:
            raise FileNotFoundError(f"Include file {full_path} not found")
        return included_content

    prompt = re.sub(include_pattern, replace_include, prompt)

    if include_general_context:
        general_content = open_file('coding/system_prompts/GENERAL.md')
        prompt += f"\n{general_content}"
    return prompt

def check_integrity():
    from coding.non_callable_tools.version_control import VersionControl
    vc = VersionControl()
    is_valid, issues = vc.validate_folder_integrity("GameFolder")
    if not is_valid:
        print("\n[error] FOLDER INTEGRITY ISSUES DETECTED:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n[WARNING] Proceeding with corrupted files may lead to further issues.")
        if input("Do you want to continue anyway? (y/n): ").strip().lower() != 'y':
            print("Aborting.")
            exit(1)
    else:
        print("[success] Folder integrity verified.")

def clear_python_cache():
    """
    Clear Python module cache (sys.modules) and bytecode cache (__pycache__).

    This prevents issues where cached modules don't reflect recent source code changes.
    Two-phase approach:
    1. Clear in-memory module cache (sys.modules) - FAST
    2. Clear disk bytecode cache (__pycache__, .pyc) - SLOWER
    """
    import sys
    import shutil
    import time
    import threading
    import gc
    import importlib

    # Phase 1: Clear in-memory module cache (CRITICAL - this is what fixes the issue)
    # This is fast and happens in-memory, no I/O
    modules_to_clear = [
        'GameFolder',
        'BASE_components',
        'BASE_files'
    ]
    
    cleared_count = 0
    for prefix in modules_to_clear:
        # Create list first to avoid "dictionary changed size during iteration"
        modules_to_remove = [key for key in sys.modules.keys() if key.startswith(prefix)]
        for module_name in modules_to_remove:
            try:
                del sys.modules[module_name]
                cleared_count += 1
            except KeyError:
                pass  # Already removed
    
    # Invalidate import system caches (path finder, loader caches)
    # This ensures Python recognizes file changes immediately
    importlib.invalidate_caches()
    
    # Force garbage collection to clean up old module objects
    # This releases memory from deleted modules
    gc.collect()
    
    print(f"Cleared {cleared_count} modules from sys.modules")

    # Phase 2: Clear disk cache (optional but helps ensure consistency)
    # Only do this from main thread to avoid threading issues
    if threading.current_thread() != threading.main_thread():
        print("Skipping disk cache clearing from background thread")
        return

    start_time = time.time()
    timeout = 1.5  # Short timeout for disk operations

    target_dirs = ["GameFolder", "BASE_components"]

    for target_dir in target_dirs:
        if time.time() - start_time > timeout:
            print("Disk cache clearing timed out - continuing")
            break

        if not os.path.exists(target_dir):
            continue

        # Use os.walk for better control and performance
        for root, dirs, files in os.walk(target_dir):
            if time.time() - start_time > timeout:
                break
            
            # Remove __pycache__ directories
            if '__pycache__' in dirs:
                cache_path = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(cache_path)
                except Exception:
                    pass  # Ignore errors, not critical
            
            # Remove .pyc files (usually inside __pycache__ but check anyway)
            for file in files:
                if file.endswith('.pyc'):
                    try:
                        os.remove(os.path.join(root, file))
                    except Exception:
                        pass  # Ignore errors

    elapsed = time.time() - start_time
    print(f"Cache clearing completed in {elapsed:.2f}s")

def cleanup_old_logs():
    """Remove old log files, keeping only the most recent server.log."""
    try:
        # Find all server log files
        server_logs = glob.glob("server*.log")

        if len(server_logs) > 1:
            # Sort by modification time, keep the newest one
            server_logs.sort(key=os.path.getmtime, reverse=True)

            # Remove all but the most recent
            for old_log in server_logs[1:]:
                try:
                    os.remove(old_log)
                    print(f"Removed old server log: {old_log}")
                except OSError as e:
                    print(f"Failed to remove {old_log}: {e}")

    except Exception as e:
        print(f"Log cleanup failed: {e}")

def should_skip_item(item_name: str) -> bool:
    """Check if an item should be skipped during backup."""
    # Skip cache directories
    if item_name in {
        '__pycache__', '.pytest_cache', '.git', 'node_modules', 
        '.cursor', '__docs', '__game_backups', '__patches', 
        '__server_patches', '__TEMP_SECURITY_BACKUP', '__config',
        'dist', 'build'
    }:
        return True
    
    # Skip hidden files and cache files
    if (item_name.startswith('.') or 
        item_name in {'.DS_Store', 'tt.py'} or
        item_name.endswith('.bak')):
        return True
    
    return False

def copytree_filtered(src: str, dst: str, should_skip_func):
    """Copy directory tree while filtering out cache files."""
    os.makedirs(dst, exist_ok=True)
    
    for root, dirs, files in os.walk(src):
        # Filter directories in-place
        dirs[:] = [d for d in dirs if not should_skip_func(d)]
        
        # Calculate relative path for destination
        rel_path = os.path.relpath(root, src)
        if rel_path == '.':
            dest_root = dst
        else:
            dest_root = os.path.join(dst, rel_path)
        
        # Create destination directory
        os.makedirs(dest_root, exist_ok=True)
        
        # Copy files (filtering already done in dirs[:] above)
        for file in files:
            if should_skip_func(file):
                continue
            src_file = os.path.join(root, file)
            dst_file = os.path.join(dest_root, file)
            shutil.copy2(src_file, dst_file)