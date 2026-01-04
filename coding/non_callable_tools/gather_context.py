from coding.tools.file_handling import get_tree_directory, read_file
import os

def gather_context_planning():
    string = f"""
    Directory Tree:
    {get_tree_directory("GameFolder")}

    """
    # read every file in the BASE_components directory
    base_components_path = "BASE_components"
    for filename in os.listdir(base_components_path):
        if filename.endswith('.py') and not filename.startswith('__'):
            filepath = os.path.join(base_components_path, filename)
            string += f"{read_file(filepath)}\n"

    string += f"{read_file('GameFolder/arenas/GAME_arena.py')}\n"
    string += f"{read_file('GameFolder/characters/GAME_character.py')}\n"
    string += f"{read_file('GameFolder/projectiles/GAME_projectile.py')}\n"
    string += f"{read_file('GameFolder/weapons/GAME_weapon.py')}\n"

    # Add key setup and configuration files that planners need
    string += f"\nSetup Configuration:\n{read_file('GameFolder/setup.py')}\n"

    return string

def gather_context_coding():
    string = f"""
    Directory Tree:
    {get_tree_directory("GameFolder")}
    """

    return string