import os
import ast
import re
from pathlib import Path
from coding.tools.security import is_file_allowed, is_directory_allowed

def find_function_usages(function_name: str, directory_path: str):
    """
    Finds all usages of a specific function name within a directory and its subdirectories.

    Args:
        function_name: The name of the function to search for.
        directory_path: The directory to search in.

    Returns:
        dict: A dictionary mapping file paths to lists of line numbers where the function is mentioned.
    """
    print(f"[TOOL LOG] find_function_usages called with:")
    print(f"  function_name: {function_name}")
    print(f"  directory_path: {directory_path}")
    if not is_directory_allowed(directory_path, operation="read"):
        result = {"error": f"Path '{directory_path}' is not allowed for reading."}
        print(f"[TOOL LOG] find_function_usages output: {result}")
        return result
    
    usages = {}
    
    # Simple regex to find the function name as a whole word (not perfect but good for simple cases)
    # This will match function calls and mentions, but might also match strings or comments.
    pattern = re.compile(rf'\b{re.escape(function_name)}\b')
    
    try:
        for root, dirs, files in os.walk(directory_path):
            # Filter directories for security and common ignores
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != "__pycache__"]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                file_path = os.path.join(root, file)
                if not is_file_allowed(file_path, operation="read"):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    file_line_matches = []
                    for i, line in enumerate(lines):
                        if pattern.search(line):
                            file_line_matches.append(i + 1)
                    
                    if file_line_matches:
                        usages[file_path] = file_line_matches
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
                    
        print(f"[TOOL LOG] find_function_usages output: {len(usages)} files with function usages found")
        return usages
    except Exception as e:
        result = {"error": f"An error occurred during search: {str(e)}"}
        print(f"[TOOL LOG] find_function_usages output: {result}")
        return result

def get_function_source(file_path: str, function_name: str):
    """
    Retrieves the source code of a specific function from a file.

    Args:
        file_path: The path to the Python file.
        function_name: The name of the function to retrieve.

    Returns:
        str: The source code of the function, or an error message.
    """
    print(f"[TOOL LOG] get_function_source called with:")
    print(f"  file_path: {file_path}")
    print(f"  function_name: {function_name}")
    if not is_file_allowed(file_path, operation="read"):
        result = f"Error: Path '{file_path}' is not allowed for reading."
        print(f"[TOOL LOG] get_function_source output: {result}")
        return result
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
            
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                lines = source.splitlines()
                start = node.lineno - 1
                end = node.end_lineno
                function_lines = lines[start:end]
                
                # Calculate dynamic width for line numbers
                total_lines = len(function_lines)
                width = len(str(node.lineno + total_lines - 1))
                
                # Format with line numbers
                numbered_lines = []
                for i, line in enumerate(function_lines):
                    line_num = node.lineno + i
                    numbered_lines.append(f"{line_num:{width}}|{line}")
                
                result = f"{file_path}\n" + "\n".join(numbered_lines)
                print(f"[TOOL LOG] get_function_source output: {len(result)} characters of function source code")
                return result
    except SyntaxError:
        result = f"Error: Syntax error in file {file_path}."
        print(f"[TOOL LOG] get_function_source output: {result}")
        return result
    except Exception as e:
        result = f"Error: {str(e)}"
        print(f"[TOOL LOG] get_function_source output: {result}")
        return result

def list_functions_in_file(file_path: str):
    """
    Lists all function names defined in a specific file.

    Args:
        file_path: The path to the Python file.

    Returns:
        list or str: A list of function names, or an error message.
    """
    print(f"[TOOL LOG] list_functions_in_file called with:")
    print(f"  file_path: {file_path}")
    if not is_file_allowed(file_path, operation="read"):
        result = f"Error: Path '{file_path}' is not allowed for reading."
        print(f"[TOOL LOG] list_functions_in_file output: {result}")
        return result
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
            
        tree = ast.parse(source)
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        print(f"[TOOL LOG] list_functions_in_file output: {len(functions)} functions found")
        return functions
    except SyntaxError:
        result = f"Error: Syntax error in file {file_path}."
        print(f"[TOOL LOG] list_functions_in_file output: {result}")
        return result
    except Exception as e:
        result = f"Error: {str(e)}"
        print(f"[TOOL LOG] list_functions_in_file output: {result}")
        return result

