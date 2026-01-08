import glob
import os


def open_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    # opens an .md or .py ecc file and returns the content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content

def load_prompt(prompt_file: str, include_general_context: bool = True) -> str:
    prompt = open_file(prompt_file)
    if include_general_context:
        general_content = open_file('coding/system_prompts/GENERAL.md')
        prompt += f"\n{general_content}"
    return prompt

def check_integrity():
    from coding.non_callable_tools.version_control import VersionControl
    vc = VersionControl()
    is_valid, issues = vc.validate_folder_integrity("GameFolder")
    if not is_valid:
        print("\n❌ FOLDER INTEGRITY ISSUES DETECTED:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n[WARNING] Proceeding with corrupted files may lead to further issues.")
        if input("Do you want to continue anyway? (y/n): ").strip().lower() != 'y':
            print("Aborting.")
            exit(1)
    else:
        print("✅ Folder integrity verified.")

def clear_python_cache():
    """
    Clear Python bytecode cache (__pycache__ directories) to ensure fresh imports.

    This prevents issues where cached bytecode doesn't reflect recent source code changes,
    especially imports like 'import math' that were added after the .pyc files were created.
    """
    import shutil
    import glob
    import time

    start_time = time.time()
    timeout = 2.0  # Very short timeout to avoid hanging

    # Only clear cache in specific directories that matter for our game
    # Be very conservative - only clear if we're in the main thread
    import threading
    if threading.current_thread() != threading.main_thread():
        print("Skipping cache clearing from background thread")
        return

    target_dirs = ["GameFolder"]  # Only clear GameFolder cache to minimize conflicts

    for target_dir in target_dirs:
        if time.time() - start_time > timeout:
            print("Cache clearing timed out - continuing with tests")
            return

        if not os.path.exists(target_dir):
            continue

        # Find __pycache__ directories in this target directory
        cache_dirs = glob.glob(f"{target_dir}/**/__pycache__", recursive=True)

        # Remove cache directories
        for cache_dir in cache_dirs:
            if time.time() - start_time > timeout:
                break
            try:
                shutil.rmtree(cache_dir)
                print(f"Cleared cache: {cache_dir}")
            except Exception as e:
                # Silently ignore cache clearing errors - not critical for testing
                pass

        # Find .pyc files in this target directory
        pyc_files = glob.glob(f"{target_dir}/**/*.pyc", recursive=True)

        # Remove individual .pyc files (limit to first 50 to avoid hanging)
        for i, pyc_file in enumerate(pyc_files[:50]):
            if time.time() - start_time > timeout:
                break
            try:
                os.remove(pyc_file)
            except Exception as e:
                # Silently ignore - not critical for testing
                pass

    # Critical: Add delay to let file system operations complete before imports
    time.sleep(1.0)
    print("Cache clearing completed - waiting for file system to settle")

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
