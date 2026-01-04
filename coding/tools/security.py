from pathlib import Path

def is_path_safe(path: str, operation: str = "read") -> bool:
    """
    Checks if the given path is allowed.
    - 'read' operations allow GameFolder and BASE_components.
    - 'write' operations ONLY allow GameFolder.
    """
    print(f"[TOOL LOG] is_path_safe called with:")
    print(f"  path: {path}")
    print(f"  operation: {operation}")
    try:
        # Get the absolute, resolved path of the target
        target_path = Path(path).resolve()
    except Exception:
        # If the path is invalid or cannot be resolved, assume it's unsafe
        result = False
        print(f"[TOOL LOG] is_path_safe output: {result}")
        return result
    
    # Get the absolute path of the project root
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    
    game_folder = (project_root / "GameFolder").resolve()
    base_components = (project_root / "BASE_components").resolve()
    
    # Check if target_path is under game_folder
    try:
        target_path.relative_to(game_folder)
        result = True
        print(f"[TOOL LOG] is_path_safe output: {result}")
        return result
    except ValueError:
        pass

    # If it's a read operation, also allow BASE_components
    if operation == "read":
        try:
            target_path.relative_to(base_components)
            result = True
            print(f"[TOOL LOG] is_path_safe output: {result}")
            return result
        except ValueError:
            pass

    # If we get here, the path is forbidden.
    # Provide a helpful message about what IS allowed to prevent guessing.
    allowed_zones = ["GameFolder", "BASE_components"] if operation == "read" else ["GameFolder"]
    error_msg = f"Error: Access to '{path}' is denied. You only have access to: {allowed_zones}. Use get_tree_directory('GameFolder') to start."
    print(f"[TOOL LOG] is_path_safe output: False ({error_msg})")
    # Note: We return False for the boolean checks, but we should probably 
    # handle this message in the calling tools.
    return False

def is_directory_allowed(path: str, operation: str = "read") -> bool | str:
    """
    Only allow directories that are in the allowed zones based on operation.
    """
    print(f"[TOOL LOG] is_directory_allowed called with:")
    print(f"  path: {path}")
    print(f"  operation: {operation}")
    
    if is_path_safe(path, operation):
        return True
    
    allowed_zones = ["GameFolder", "BASE_components"] if operation == "read" else ["GameFolder"]
    return f"Error: Path '{path}' is outside of allowed zones {allowed_zones}. Start exploration at 'GameFolder' or 'BASE_components'."

def is_file_allowed(path: str, operation: str = "read") -> bool | str:
    """
    Only allow files that are in the allowed zones based on operation.
    """
    print(f"[TOOL LOG] is_file_allowed called with:")
    print(f"  path: {path}")
    print(f"  operation: {operation}")
    
    if is_path_safe(path, operation):
        return True
        
    allowed_zones = ["GameFolder", "BASE_components"] if operation == "read" else ["GameFolder"]
    return f"Error: Path '{path}' is outside of allowed zones {allowed_zones}. You can only access files within these directories."
