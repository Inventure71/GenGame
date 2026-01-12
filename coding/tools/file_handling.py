import os
from coding.tools.security import is_file_allowed, is_directory_allowed
from coding.non_callable_tools.action_logger import action_logger

def create_file(path: str = None, **kwargs):
    """
    Creates an empty file at the specified path if the path is allowed.
    
    IMPORTANT: This function ONLY creates an EMPTY file. It does NOT accept content.
    To write content to a file, use modify_file_inline after creating the file.
    
    CORRECT USAGE:
        create_file(path="GameFolder/new_file.py")  # Creates empty file
        modify_file_inline(file_path="...", diff_text="...")  # Then write content

    Args:
        path (str): The file path to create. This is the ONLY accepted parameter.
                   Do NOT use 'file_path', 'filepath', or 'filename'.

    Returns:
        str: A success message if the file was created, or an error message if failed.
    """
    print(f"[TOOL LOG] create_file called with:")
    print(f"  path: {path}")
    if kwargs:
        print(f"  UNEXPECTED kwargs: {list(kwargs.keys())}")
    
    # --- Check for incorrect parameter names (common LLM mistakes) ---
    if kwargs:
        wrong_params = list(kwargs.keys())
        suggestions = []
        
        # Common wrong parameter names
        path_aliases = {'file_path', 'filepath', 'file', 'filename', 'target_file', 'target_path', 'file_name'}
        content_params = {'content', 'contents', 'text', 'data', 'code', 'file_content'}
        
        has_content_param = False
        for param in wrong_params:
            param_lower = param.lower()
            if param_lower in content_params or 'content' in param_lower:
                has_content_param = True
                suggestions.append(f"  - '{param}': This tool does NOT accept content! It only creates EMPTY files.")
            elif param_lower in path_aliases or 'path' in param_lower or 'file' in param_lower:
                suggestions.append(f"  - '{param}' → use 'path' instead")
                # Auto-recover: use the wrong param as path if path is missing
                if path is None:
                    path = kwargs[param]
                    suggestions.append(f"    (Auto-recovered: using '{param}' value as path)")
            else:
                suggestions.append(f"  - '{param}' is not a valid parameter")
        
        warning_msg = (
            f"WARNING: Received unexpected parameter(s): {wrong_params}\n"
            f"This tool ONLY accepts ONE parameter:\n"
            f"  • path (str): The file path to create\n"
            f"\n⚠️  This tool creates EMPTY files only! To write content:\n"
            f"  1. Call create_file(path='...') to create empty file\n"
            f"  2. Call modify_file_inline(file_path='...', diff_text='...') to add content\n"
            f"\nParameter issues:\n" + "\n".join(suggestions)
        )
        print(f"[TOOL LOG] {warning_msg}")
        
        # If content was passed, we can still create the empty file but warn loudly
        if has_content_param and path:
            print(f"[TOOL LOG] Creating empty file (ignoring content). Use modify_file_inline next!")
        elif path is None:
            result = f"Error: {warning_msg}"
            print(f"[TOOL LOG] create_file output: {result}")
            return result
    
    # --- Validate path ---
    if not path:
        result = (
            "Error: Missing required 'path' argument.\n"
            "Usage: create_file(path='GameFolder/new_file.py')\n"
            "Note: This creates an EMPTY file. Use modify_file_inline to add content."
        )
        print(f"[TOOL LOG] create_file output: {result}")
        return result
    
    allowed = is_file_allowed(path, operation="write")
    if allowed is not True:
        result = f"Error: Failed to create file: {allowed}"
        print(f"[TOOL LOG] create_file output: {result}")
        return result

    os.makedirs(os.path.dirname(path), exist_ok=True)

    action_logger.snapshot_file(path)
    
    with open(path, 'w') as f:
        f.write('')

    action_logger.record_file_change(path)

    result = f"Successfully created empty file: {path}\nNOTE: Use modify_file_inline(file_path='{path}', diff_text='...') to add content."
    print(f"[TOOL LOG] create_file output: {result}")
    return result

def read_file(file_path: str, start_line: int = None, end_line: int = None):
    """
    Reads and returns the content of the file at the specified path if allowed.
    Lines are prefixed with line numbers for easier diff creation.

    Args:
        file_path: The file path to read.
        start_line: Optional starting line number (1-indexed, inclusive). If None, reads from the beginning.
        end_line: Optional ending line number (1-indexed, inclusive). If None, reads to the end.

    Returns:
        str: The file content with line numbers, or an error message if the file_path is not allowed or the file doesn't exist.

    Note: When using line ranges, consider expanding the range beyond what you need for better context.
          Example: If you need lines 16-20, request 10-30 to see surrounding code.
    """
    print(f"[TOOL LOG] read_file called with:")
    print(f"  file_path: {file_path}")
    print(f"  start_line: {start_line}")
    print(f"  end_line: {end_line}")

    allowed = is_file_allowed(file_path)
    if allowed is not True:
        result = f"Error: Failed to read file: {allowed}"
        print(f"[TOOL LOG] read_file output: {result}")
        return result
        
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            total_lines = len(lines)
            
            # Calculate dynamic width based on total lines for efficiency
            width = len(str(total_lines))
            
            # Handle line range parameters
            if start_line is not None or end_line is not None:
                # Convert to 0-indexed and handle bounds
                start_idx = max(0, (start_line - 1) if start_line else 0)
                end_idx = min(total_lines, end_line if end_line else total_lines)
                
                # Validate range
                if start_idx >= total_lines:
                    result = f"Error: start_line {start_line} exceeds file length ({total_lines} lines)"
                    print(f"[TOOL LOG] read_file output: {result}")
                    return result
                
                lines_subset = lines[start_idx:end_idx]
                content_lines = "".join([f"{i+start_idx+1:{width}}|{line}" for i, line in enumerate(lines_subset)])
                result = f"{file_path} (lines {start_idx+1}-{end_idx} of {total_lines})\n{content_lines}"
                print(f"[TOOL LOG] read_file output: {len(result)} characters (lines {start_idx+1}-{end_idx} of {total_lines})")
            else:
                # Read entire file
                content_lines = "".join([f"{i+1:{width}}|{line}" for i, line in enumerate(lines)])
                result = f"{file_path}\n{content_lines}"
                print(f"[TOOL LOG] read_file output: {len(result)} characters of file content")

            return result
    except FileNotFoundError:
        result = f"Error: File not found: {file_path}"
        print(f"[TOOL LOG] read_file output: {result}")
        return result

def get_directory(path: str):
    """
    Lists the immediate contents (files and directories) of the specified path if allowed.
    Filters out hidden files (starting with '.') and '__pycache__'.

    Args:
        path: The directory path to list.

    Returns:
        list or str: A list of names in the directory, or an error message if the path is not allowed.
    """
    print(f"[TOOL LOG] get_directory called with:")
    print(f"  path: {path}")
    
    allowed = is_directory_allowed(path)
    if allowed is not True:
        result = f"Error: Failed to get directory contents: {allowed}"
        print(f"[TOOL LOG] get_directory output: {result}")
        return result
        
    try:
        items = os.listdir(path)
        result = [item for item in items if not item.startswith('.') and item != "__pycache__"]
        print(f"[TOOL LOG] get_directory output: {len(result)} items found")
        return result
    except Exception as e:
        result = f"Error listing directory: {e}"
        print(f"[TOOL LOG] get_directory output: {result}")
        return result

def get_tree_directory(path: str):
    """
    Returns a visual tree representation of the directory structure starting from the specified path.
    Ignores hidden files (starting with '.') and '__pycache__' folders.

    Args:
        path: The root directory path for the tree.

    Returns:
        str: A string representing the directory tree, or an error message if the path is not allowed.
    """
    print(f"[TOOL LOG] get_tree_directory called with:")
    print(f"  path: {path}")
    
    allowed = is_directory_allowed(path)
    if allowed is not True:
        result = f"Error: Failed to get tree directory: {allowed}"
        print(f"[TOOL LOG] get_tree_directory output: {result}")
        return result
    
    def build_tree(current_path, prefix=""):
        tree_str = ""
        try:
            # Filter items immediately
            items = sorted([
                item for item in os.listdir(current_path) 
                if not item.startswith('.') and item != "__pycache__" and not item.endswith('.bak')
            ])
        except Exception as e:
            return f"Error: accessing {current_path}: {e}\n"
            
        for i, item in enumerate(items):
            item_path = os.path.join(current_path, item)
            
            is_last = (i == len(items) - 1)
            connector = "|__ " if is_last else "|-- "
            
            tree_str += f"{prefix}{connector}{item}\n"
            
            if os.path.isdir(item_path):
                new_prefix = prefix + ("    " if is_last else "|   ")
                tree_str += build_tree(item_path, new_prefix)
        return tree_str

    root_name = os.path.basename(os.path.abspath(path))
    result = f"{root_name}\n{build_tree(path)}"
    print(f"[TOOL LOG] get_tree_directory output: {len(result)} characters of tree structure")
    return result
