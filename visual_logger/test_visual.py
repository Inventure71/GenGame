#!/usr/bin/env python3
"""
Realistic Visual Logger Test - Simulates actual AI agent workflow exactly as the real model handlers work
"""
from coding.non_callable_tools.action_logger import action_logger
from coding.non_callable_tools.todo_list import TodoList
from coding.tools.testing import run_all_tests_tool as run_all_tests
import time
import random

error_scenarios = [
    {
        "name": "read_file", 
        "args": {"path": "/etc/passwd"},
        "description": "Unauthorized system file access"
    },
    {
        "name": "get_tree_directory", 
        "args": {"path": "/System/Library"},
        "description": "Forbidden directory access"
    },
    {
        "name": "read_file", 
        "args": {"path": "nonexistent_file_that_definitely_does_not_exist.py"},
        "description": "Reading non-existent file"
    },
    {
        "name": "list_functions_in_file", 
        "args": {"file_path": "file_that_does_not_exist.py"},
        "description": "Analyzing non-existent file"
    },
    # Keep simulated write errors for safety
    {
        "name": "create_file", 
        "args": {"path": "/etc/malicious_file.py"},
        "description": "Attempting to create file in system directory"
    },
    {
        "name": "modify_file_inline", 
        "args": {
            "file_path": "nonexistent_file.py",
            "diff_text": "@@ -1,3 +1,4 @@\nprint('hello')"
        },
        "description": "Modifying non-existent file"
    }
]

def simulate_model_thinking(thought):
    """Simulate model thinking with realistic delays"""
    action_logger.log_thinking(thought)
    time.sleep(random.uniform(0.8, 2.0))

def simulate_model_response(text):
    """Simulate model text response"""
    action_logger.log_model_text(text)
    time.sleep(random.uniform(0.5, 1.2))

def generate_tool_result(tool_name, args):
    """Generate realistic results - ACTUALLY CALL REAL TOOLS for read operations"""
    
    try:
        # READ-ONLY OPERATIONS: Call actual tools for realistic results
        if tool_name == "read_file":
            from coding.tools.file_handling import read_file
            return read_file(**args)
            
        elif tool_name == "get_tree_directory":
            from coding.tools.file_handling import get_tree_directory
            return get_tree_directory(**args)
            
        elif tool_name == "list_functions_in_file":
            from coding.tools.code_analysis import list_functions_in_file
            result = list_functions_in_file(**args)
            if isinstance(result, list):
                return f"Functions in {args.get('file_path', 'file')}: {', '.join(result)}"
            return result

        elif tool_name == "find_function_usages":
            from coding.tools.code_analysis import find_function_usages
            result = find_function_usages(**args)
            if isinstance(result, dict):
                if "error" in result:
                    return f"Error: {result['error']}"
                count = sum(len(lines) for lines in result.values())
                return f"Found {count} usages of '{args.get('function_name', 'func')}' in {len(result)} files"
            return result

        elif tool_name == "get_function_source":
            from coding.tools.code_analysis import get_function_source
            return get_function_source(**args)
            
        elif tool_name == "run_all_tests":
            # Use mock for testing (real run_all_tests requires pygame)
            result = {'success': True, 'total_tests': 5, 'passed_tests': 5, 'failed_tests': 0}
            # Convert dict result to string format expected by logger
            if isinstance(result, dict):
                success_status = "✓ PASSED" if result.get("success", False) else "✗ FAILED"
                return f"Tests completed: {success_status}\nTotal: {result.get('total_tests', 0)} tests"
            return str(result)
            
        # WRITE OPERATIONS: Keep simulated (don't actually modify files)
        elif tool_name == "create_file":
            file_path = args.get('path', '')
            if '/etc/' in file_path or '/System/' in file_path:
                return f"Error: Failed to create file: {file_path} - Path not allowed. You can only write to GameFolder."
            if 'readonly' in file_path:
                return f"Error: Failed to create file: {file_path} - Permission denied."
            return f"Successfully created empty file: {file_path}\nNOTE: Use modify_file_inline(file_path='{file_path}', diff_text='...') to add content."
            
        elif tool_name == "modify_file_inline":
            file_path = args.get('file_path', '')
            if 'nonexistent' in file_path:
                return f"Error: File not found at path: {file_path}"
            if '/etc/' in file_path:
                return f"Error: Failed to modify file: {file_path} - Path not allowed."
            diff_text = args.get('diff_text', '')
            if 'invalid_diff_format' in diff_text:
                return "Error: Invalid unified diff format. Missing required @@ headers."
            if 'syntax_error' in diff_text:
                return "Error: syntax check failed. The patch would result in invalid Python code."
            return "Successfully modified file"
            
        elif tool_name == "complete_task":
            return "Task marked as completed. Moving to next task."
            
        else:
            return f"{tool_name} executed successfully"
            
    except Exception as e:
        # If real tool call fails, return a realistic error
        return f"Error: Tool execution failed: {str(e)}"

def simulate_model_response_with_tools(text_content, tool_calls):
    """Simulate a complete model response that includes both text and tool calls (real handler behavior)"""

    # 1. Model gives text response first
    if text_content:
        simulate_model_response(text_content)

    # 2. Extract tool calls from the response (this is what model actually does)
    extracted_tool_calls = []
    for tool_call in tool_calls:
        extracted_tool_calls.append({
            "name": tool_call["name"],
            "args": tool_call["args"]
        })

    # 3. Log the MODEL REQUEST with token usage BEFORE tool execution
    # (This happens when the model actually responds with tool calls)
    input_tokens = random.randint(800, 1500)
    output_tokens = random.randint(200, 400)
    action_logger.log_model_request(
        input_tokens,
        output_tokens,
        tool_calls=extracted_tool_calls,  # Just the calls, not results yet
        chat_history=[]  # Would be actual chat history
    )

    # 4. Execute ALL tool calls sequentially (as the real handler does)
    tool_results = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]

        # Generate result
        result = generate_tool_result(tool_name, args)

        # Convert result to string if it's not already (handle None, lists, dicts)
        if result is None:
            result_str = "Error: Tool returned None"
            success = False
        else:
            result_str = str(result)
            # Determine success based on result (like real handlers do)
            if result_str.startswith("Error:"):
                success = False
            else:
                success = True

        # Log INDIVIDUAL tool execution (this is what the handler does for each tool)
        action_logger.log_action(tool_name, args, result_str, success=success)

        tool_results.append({
            "name": tool_name,
            "args": args,
            "result": result_str,
            "success": success
        })

    return tool_results

def simulate_parallel_tool_calls(tool_calls):
    """Legacy function - now just calls the new simulation without text"""
    return simulate_model_response_with_tools(None, tool_calls)

def simulate_task_completion(todo_list, task_description):
    """Simulate completing a TODO task"""
    print(f"[success] Completing task: {task_description}")
    simulate_parallel_tool_calls([{
        "name": "complete_task",
        "args": {
            "summary": f"- Completed task: {task_description}\n- This is a test simulation summary that meets the minimum 150 character requirement for the complete_task function call."
        }
    }])
    todo_list.complete_task(f"- Completed task: {task_description}\n- This is a test simulation summary that meets the minimum 150 character requirement for the complete_task function call.")

def main():
    print("🎯 Starting REALISTIC Visual Logger Test...")
    print("This simulates actual AI agent behavior with parallel tool calls and task completion")
    print("\n🌐 Open http://127.0.0.1:8765 to see the live visualization!")

    # Initialize TODO list and connect to logger
    todo_list = TodoList()
    action_logger.set_todo_list(todo_list)

    # Start the session
    action_logger.start_session(visual=True)
    print("[success] Session started - Visual Logger active")

    try:
        # PHASE 1: Initial Analysis and Planning
        print("\n📋 PHASE 1: Analysis & Planning")
        simulate_model_thinking("User wants to add a 'Plasma Blaster' weapon. I need to analyze the existing codebase to understand the weapon system architecture.")

        # Add comprehensive TODOs
        todo_list.append_to_todo_list(
            "Analyze weapon architecture",
            "Examine BASE_weapon.py, GAME_weapon.py, and existing weapon implementations"
        )
        todo_list.append_to_todo_list(
            "Design Plasma Blaster",
            "Design the Plasma Blaster class with unique mechanics (rapid fire, overheating)"
        )
        todo_list.append_to_todo_list(
            "Implement PlasmaProjectile",
            "Create PlasmaProjectile with particle effects and area damage"
        )
        todo_list.append_to_todo_list(
            "Add weapon balancing",
            "Implement overheating mechanic and cooldown system"
        )
        todo_list.append_to_todo_list(
            "Integrate with game",
            "Register weapon in setup.py and add to weapon selection"
        )
        todo_list.append_to_todo_list(
            "Create comprehensive tests",
            "Test weapon mechanics, overheating, projectile behavior"
        )

        simulate_model_response("I've broken this down into manageable tasks. Let me start by deeply analyzing the weapon system.")

        # PHASE 2: Deep Codebase Analysis (PARALLEL TOOL CALLS!)
        print("\n🔍 PHASE 2: Deep Codebase Analysis")
        simulate_model_thinking("I need to understand the weapon system thoroughly. Let me read multiple key files in parallel to get the complete picture.")

        # Simulate model responding with MULTIPLE tool calls in ONE response
        parallel_analysis = [
            {"name": "read_file", "args": {"file_path": "BASE_components/BASE_weapon.py"}},
            {"name": "read_file", "args": {"file_path": "GameFolder/weapons/GAME_weapon.py"}},
            {"name": "get_tree_directory", "args": {"path": "GameFolder/weapons"}},
            {"name": "list_functions_in_file", "args": {"file_path": "GameFolder/weapons/BlackHoleGun.py"}},
        ]

        simulate_model_response_with_tools(
            "I'll analyze the weapon system by examining the base classes and existing implementations.",
            parallel_analysis
        )

        # More parallel analysis - model responds with text + more tool calls
        parallel_inspection = [
            {"name": "find_function_usages", "args": {"function_name": "fire", "directory_path": "GameFolder/weapons"}},
            {"name": "get_function_source", "args": {"file_path": "GameFolder/weapons/TornadoGun.py", "function_name": "fire"}},
            {"name": "read_file", "args": {"file_path": "BASE_components/BASE_projectile.py"}},
        ]

        simulate_model_response_with_tools(
            "Now let me examine how the fire() method works and look at projectile implementation.",
            parallel_inspection
        )

        # Complete analysis task
        simulate_task_completion(todo_list, "Analyze weapon architecture")

        # PHASE 2.5: Error Handling Demonstration
        print("\n[error] PHASE 2.5: Error Handling")
        simulate_model_thinking("Let me demonstrate what happens when tools fail - trying unauthorized access and invalid operations.")

        simulate_model_response_with_tools(
            "Let me show you how the system handles various error conditions and security restrictions.",
            error_scenarios
        )

        print("[success] Error handling demonstrated - check the visual logger for red 'failed' indicators")

        # PHASE 3: Design and Implementation
        print("\n⚙️ PHASE 3: Design & Implementation")
        simulate_model_thinking("Now I understand the architecture. For the Plasma Blaster, I'll implement: rapid-fire capability, overheating mechanic, and plasma projectiles with area damage.")

        # File operations for Plasma Blaster
        action_logger.snapshot_file("GameFolder/weapons/GAME_weapon.py")

        # Create the weapon file
        simulate_parallel_tool_calls([{
            "name": "create_file",
            "args": {"path": "GameFolder/weapons/PlasmaBlaster.py"}
        }])

        # Implement the weapon class
        plasma_blaster_code = '''@@ -0,0 +1,45 @@
class PlasmaBlaster(Weapon):
    def __init__(self):
        super().__init__()
        self.name = "Plasma Blaster"
        self.damage = 15
        self.cooldown = 0.1  # Very fast firing
        self.max_heat = 100
        self.current_heat = 0
        self.heat_per_shot = 8
        self.cooling_rate = 25  # Heat per second
        self.overheated = False

    def fire(self, position, direction):
        if self.overheated:
            return None  # Can't fire when overheated

        # Add heat
        self.current_heat += self.heat_per_shot
        if self.current_heat >= self.max_heat:
            self.overheated = True
            self.current_heat = self.max_heat

        # Create plasma projectile
        return PlasmaProjectile(position, direction, self.damage)

    def update(self, dt):
        super().update(dt)

        # Cooling system
        if self.current_heat > 0:
            self.current_heat -= self.cooling_rate * dt
            if self.current_heat <= 0:
                self.current_heat = 0
                self.overheated = False

    def get_heat_percentage(self):
        return self.current_heat / self.max_heat
'''

        simulate_parallel_tool_calls([{
            "name": "modify_file_inline",
            "args": {
                "file_path": "GameFolder/weapons/PlasmaBlaster.py",
                "diff_text": plasma_blaster_code
            }
        }])

        action_logger.record_file_change("GameFolder/weapons/PlasmaBlaster.py")

        # Create the projectile simultaneously
        simulate_parallel_tool_calls([{
            "name": "create_file",
            "args": {"path": "GameFolder/projectiles/PlasmaProjectile.py"}
        }])

        plasma_projectile_code = '''@@ -0,0 +1,35 @@
class PlasmaProjectile(Projectile):
    def __init__(self, position, direction, damage):
        super().__init__(position, direction)
        self.speed = 600
        self.damage = damage
        self.color = (0, 150, 255)  # Bright blue plasma
        self.radius = 8
        self.lifetime = 3.0
        self.area_damage = damage * 0.6  # 60% damage in area
        self.area_radius = 30

    def update(self, dt):
        super().update(dt)

        # Plasma effect: slight random movement
        import random
        self.velocity.x += random.uniform(-20, 20) * dt
        self.velocity.y += random.uniform(-20, 20) * dt

    def on_collision(self, target):
        # Deal direct damage
        if hasattr(target, 'take_damage'):
            target.take_damage(self.damage)

        # Deal area damage to nearby enemies
        # (Implementation would check for enemies within area_radius)

        # Remove projectile
        self.destroy()

    def render(self, screen):
        import pygame
        # Draw plasma ball with glow effect
        pygame.draw.circle(screen, self.color, self.position, self.radius)
        pygame.draw.circle(screen, (100, 200, 255), self.position, self.radius + 3, 2)
'''

        simulate_parallel_tool_calls([{
            "name": "modify_file_inline",
            "args": {
                "file_path": "GameFolder/projectiles/PlasmaProjectile.py",
                "diff_text": plasma_projectile_code
            }
        }])

        action_logger.record_file_change("GameFolder/projectiles/PlasmaProjectile.py")

        # Complete design tasks
        simulate_task_completion(todo_list, "Design Plasma Blaster")
        simulate_task_completion(todo_list, "Implement PlasmaProjectile")

        # PHASE 4: Integration
        print("\n🔗 PHASE 4: Integration")
        simulate_model_thinking("Now I need to register the new weapon in the game setup. Let me check the current setup and add the Plasma Blaster.")

        # Model responds with tools to check setup
        integration_tools = [
            {"name": "read_file", "args": {"file_path": "GameFolder/setup.py"}},
            {"name": "list_functions_in_file", "args": {"file_path": "GameFolder/setup.py"}},
        ]

        simulate_model_response_with_tools(
            "Let me examine the setup.py file to understand how to register the new Plasma Blaster weapon.",
            integration_tools
        )

        # Update setup.py
        setup_modification = '''@@ -15,6 +15,8 @@
 from weapons.TornadoGun import TornadoGun
 from weapons.PhaseDisruptor import PhaseDisruptor
 from weapons.Sword import Sword
+from weapons.PlasmaBlaster import PlasmaBlaster
+from projectiles.PlasmaProjectile import PlasmaProjectile

 # Weapon registry
 WEAPON_REGISTRY = {
@@ -25,6 +27,7 @@
     'tornado_gun': TornadoGun,
     'phase_disruptor': PhaseDisruptor,
     'sword': Sword,
+    'plasma_blaster': PlasmaBlaster,
 }

 # Projectile registry
@@ -32,6 +35,7 @@
     'tornado_projectile': TornadoProjectile,
     'phase_projectile': PhaseProjectile,
     'sword_slash': SwordSlash,
+    'plasma_projectile': PlasmaProjectile,
 }'''

        simulate_parallel_tool_calls([{
            "name": "modify_file_inline",
            "args": {
                "file_path": "GameFolder/setup.py",
                "diff_text": setup_modification
            }
        }])

        action_logger.record_file_change("GameFolder/setup.py")

        simulate_task_completion(todo_list, "Integrate with game")

        # PHASE 5: Testing
        print("\n🧪 PHASE 5: Testing")
        simulate_model_thinking("Let me run the comprehensive test suite to make sure the Plasma Blaster works correctly and doesn't break anything.")

        # Model responds with test execution
        simulate_model_response_with_tools(
            "Time to run the full test suite to validate the Plasma Blaster implementation.",
            [{"name": "run_all_tests", "args": {}}]
        )

        simulate_task_completion(todo_list, "Create comprehensive tests")

        # Final summary
        simulate_model_response("🎉 Plasma Blaster implementation completed successfully! The weapon features rapid-fire plasma bolts with an overheating mechanic and area damage effects. All tests are passing and the weapon is now available in the game.")

        print("Running tests...")
        print(run_all_tests())

        print("\n🎯 WORKFLOW COMPLETE!")
        print("📊 The visual logger captured:")
        print("   • Model responses with parallel tool calls (realistic AI behavior)")
        print("   • Sequential tool execution (as handlers actually do)")
        print("   • Real-time file modifications and diffs")
        print("   • TODO task progress and completion")
        print("   • Token usage tracking per model request")
        print("   • Complete process flow visualization")

        print("\n🌐 Check http://127.0.0.1:8765 for the complete interactive visualization!")
        print("Press Enter to end the session...")
        input()

    except KeyboardInterrupt:
        print("\n⏹️  Session interrupted by user")

    finally:
        # End the session
        action_logger.end_session()
        print("🏁 Visual Logger session ended. Server stopped.")

if __name__ == "__main__":
    main()
