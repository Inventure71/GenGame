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
    
    # Find all __pycache__ directories
    cache_dirs = glob.glob("**/__pycache__", recursive=True)
    
    # Also find .pyc files directly (though __pycache__ dirs are more common)
    pyc_files = glob.glob("**/*.pyc", recursive=True)
    
    # Remove cache directories
    for cache_dir in cache_dirs:
        try:
            shutil.rmtree(cache_dir)
            print(f"Cleared cache: {cache_dir}")
        except Exception as e:
            print(f"Warning: Could not remove cache directory {cache_dir}: {e}")
    
    # Remove individual .pyc files (less common but possible)
    for pyc_file in pyc_files:
        try:
            os.remove(pyc_file)
        except Exception as e:
            print(f"Warning: Could not remove .pyc file {pyc_file}: {e}")