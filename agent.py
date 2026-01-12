import time
from dotenv import load_dotenv
from coding.non_callable_tools.backup_handling import BackupHandler
from coding.generic_implementation import GenericHandler
from coding.non_callable_tools.gather_context import gather_context_planning, gather_context_coding, gather_context_testing, gather_context_fix
from coding.non_callable_tools.todo_list import TodoList
from coding.tools.file_handling import get_tree_directory, read_file, create_file, get_directory
from coding.tools.modify_inline import modify_file_inline
from coding.tools.code_analysis import find_function_usages, get_function_source, list_functions_in_file
from coding.non_callable_tools.action_logger import action_logger
from coding.tools.testing import parse_test_results
from BASE_components.BASE_tests import run_all_tests
from coding.tools.testing import run_all_tests_tool
from coding.non_callable_tools.helpers import load_prompt
from coding.non_callable_tools.helpers import check_integrity

def enchancer_feature(prompt: str, modelHandler: GenericHandler):
    enchancer_sys_prompt = load_prompt("coding/system_prompts/enchancer.md")
    tools = []
    modelHandler.set_tools(tools)
    modelHandler.setup_config("MEDIUM", enchancer_sys_prompt, tools=tools)
    return modelHandler.generate_response(prompt=prompt, use_tools=False, use_history=False)

def plan_feature(prompt: str, modelHandler: GenericHandler, todo_list: TodoList, fix_mode: bool, results: dict=None):
    if fix_mode:
        print("------ Planning in fix mode ------")
        planning_sys_prompt = load_prompt("coding/system_prompts/planning_fix.md")
        context = gather_context_fix(results=results)
    else:
        print("------ Planning in normal mode ------")
        planning_sys_prompt = load_prompt("coding/system_prompts/planning.md")
        context = gather_context_planning()

    planning_tools = [
        todo_list.append_to_todo_list,
        read_file,
        find_function_usages,
        get_function_source,
        list_functions_in_file,
        get_directory,
        # get_tree_directory,  # Already provided in planning context
    ]
    
    action_logger.set_todo_list(todo_list) 
    modelHandler.set_tools(planning_tools)
    modelHandler.setup_config("HIGH", planning_sys_prompt, tools=planning_tools)
    full_prompt = (
        f"## User Request\n"
        f"{prompt}\n"
        f"{context}\n"
    )
        
    print("--------------------------------")
    print("Planning...") # the goal is to create a few tasks to be completed with a deep description
    planning_response = modelHandler.generate_response(
        prompt=full_prompt, 
        use_tools=True, 
        use_history=True
    )
    print(planning_response) 
    print("Finished planning")
    print("--------------------------------")
    
def implement_feature(modelHandler: GenericHandler, todo_list: TodoList):
    coding_sys_prompt = load_prompt("coding/system_prompts/coding.md")

    all_tools = [
        read_file, 
        create_file,
        get_directory,
        get_tree_directory,
        modify_file_inline,
        list_functions_in_file,
        find_function_usages,
        get_function_source,
        todo_list.complete_task,
    ]

    print("------ Checking if should summarize chat history... ------")
    if len(modelHandler.chat_history) > 0:
        modelHandler.summarize_chat_history(autocleanup=True)
        print("------ Summarized chat history ------")

    else:
        print("------ STRANGE No chat history to summarize STRANGE ------")
    
    print("------ Setting up coding agent ------")
    modelHandler.set_tools(all_tools)
    modelHandler.setup_config("LOW", coding_sys_prompt, tools=all_tools)
    print("Waiting 2 seconds for the API to be ready...")
    time.sleep(1)

    print("--------------------------------")
    print("\nAgent is working...\n")
        
    number_of_tasks = todo_list.get_number_of_tasks()
    current_index = todo_list.index_of_current_task

    while current_index < number_of_tasks and current_index != -1:
        print("--------------------------------")
        todo_item_str = todo_list.get_current_task()
        if todo_item_str == "No tasks remaining, all tasks have been completed":
            print("Agent has completed all tasks")
            current_index = -1
            break
        print("Agent is working on: ", todo_item_str)
        
        full_prompt = (
            f"## Current Task\n"
            f"{todo_item_str}\n"
            f"## Instructions\n"
            f"1. Implement exactly what this task specifies\n"
            f"2. Call `complete_task()` when done\n"
            f"3. Do NOT implement features beyond this task\n"
            f"{gather_context_coding()}\n"
        )
            
        current_index = modelHandler.ask_until_task_completed(todo_list, current_index, full_prompt, summarize_at_completion=True)
        print("--------------------------------")

def generate_tests(prompt: str, modelHandler: GenericHandler, todo_list: TodoList):
    all_tools = [
        read_file, 
        create_file,
        get_directory,
        get_tree_directory,
        modify_file_inline,
        list_functions_in_file,
        find_function_usages,
        get_function_source,
        todo_list.complete_task,
    ]

    print("--------------------------------")
    print("Generating tests...")
    # we add to the todo list the task of creating the tests
    todo_list.append_to_todo_list("Create tests for the newly implemented features", "Create tests for all the newly implemented features in the GameFolder/tests/ directory.")
    current_index = todo_list.index_of_current_task # this will be already set by the append_to_todo_list call
        
    modelHandler.summarize_chat_history(autocleanup=True)
    # First we generate the tests for the custom functions that were implemented
    # We still use the same tools
    modelHandler.set_tools(all_tools)
    modelHandler.setup_config("MEDIUM", load_prompt("coding/system_prompts/testing.md"), tools=all_tools)
        
    # here we make sure that it runs until the todo isn't marked as completed
    all_tasks = todo_list.get_all_tasks()
    full_prompt = (
        f"General Objective: {prompt}\n"
        f"All steps done so far: {all_tasks}\n"
        f"{gather_context_testing()}\n"
        f"Instructions: Create the tests for all the features and interactions that were implemented. "
        f"Once finished, you MUST call 'complete_task' to proceed."
    )
    print("Creating tests...")
    current_index = modelHandler.ask_until_task_completed(todo_list, current_index, full_prompt, summarize_at_completion=False)
    print("Tests created (REMEMBER THAT WE DIDN'T SUMMARIZE THE CHAT FOR NOW)")
    print("--------------------------------")

def fix_system(prompt: str, modelHandler: GenericHandler, results: dict):
    if len(modelHandler.chat_history) > 1:
        print("------ Summarizing chat history ------")
        modelHandler.summarize_chat_history(autocleanup=True)
    
    todo_list = TodoList() # brand new todo list for this fix, so that we don't clutter with useless info
    todo_list.append_to_todo_list("Fix the tests", f"Fix all the tests that failed, in particular these are the logs: {str(results['failures'])}")
    current_index = todo_list.index_of_current_task
    
    fix_sys_prompt = load_prompt("coding/system_prompts/fix_agent.md")

    all_tools = [
        read_file,
        create_file,
        get_directory,
        get_tree_directory,
        modify_file_inline,
        list_functions_in_file,
        find_function_usages,
        get_function_source,
        run_all_tests_tool,
        todo_list.complete_task,
    ]

    modelHandler.set_tools(all_tools)
    modelHandler.setup_config("MEDIUM", fix_sys_prompt, tools=all_tools)
    
    lines = [
        "## Fix Task:",
        f"{gather_context_fix(results=results)}",
        "Fix all failing tests using the debugging workflow."
        #f"{prompt}\n" # will this just be the same as above?
    ]
    if prompt:
        lines.append(f"## User Comment:\n{prompt}")

    full_prompt = "\n".join(lines)

    print("--------------------------------")
    print("PROMPT: ", full_prompt)
    print("--------------------------------")
    
    modelHandler.ask_until_task_completed(todo_list, current_index, full_prompt, summarize_at_completion=False)
    return todo_list

def full_loop(prompt: str, modelHandler: GenericHandler, todo_list: TodoList, fix_mode: bool, backup_name: str, total_cleanup: bool, results: dict=None, UI_called=False):
    """
    Main game creation loop that plans, implements, tests, and optionally fixes issues.
    
    Returns:
        tuple: (success, modelHandler, todo_list, prompt, backup_name)
            - success: True if tests passed, False if tests failed
            - modelHandler: Updated GenericHandler instance
            - todo_list: Updated TodoList instance
            - prompt: The fix prompt if tests failed, empty string otherwise
            - backup_name: Name of the backup used
    """
    if total_cleanup:
        modelHandler.clean_chat_history()

    if not fix_mode:
        # Link todo list to action logger for tracking
        action_logger.set_todo_list(todo_list)

        print("------ Enchanting prompt ------")
        prompt = enchancer_feature(prompt, modelHandler)
    
        print("--------------------------------"*5)
        print("Enchanced prompt:")
        print(prompt)
        print("--------------------------------"*5)

        plan_feature(prompt, modelHandler, todo_list, fix_mode=fix_mode, results=results)
        implement_feature(modelHandler, todo_list)
    
        generate_tests(prompt, modelHandler, todo_list)
    
    else:
        print("------ Fixing system ------")
        if results is None:
            results = run_all_tests_tool()
        todo_list = fix_system(prompt, modelHandler, results)

    results = run_all_tests_tool()
    print("Tests results: ", results)

    issues_to_fix = parse_test_results(results)
    if len(issues_to_fix) > 0:
        print("Tests failed, please fix the issues and run the tests again")
        print("Issues to fix: ", issues_to_fix)
        print("Some tests failed do you want to ask for a fix? (y/n)")
        print("You will be prompted to save the files to the extension file after the N or a successful fix")
        if not UI_called:
            answer = input("Fix tests? (y/n): ").strip().lower() == 'y'
        else:
            answer = True

        if answer:
            print("Asking for a fix to model...")
            # files involved in issues_to_fix
            fix_prompt = (
                f"## The following tests failed, understand why and fix the issues\n"
                f"{issues_to_fix}\n"
            )
            if not UI_called:
                # Recursive call for command-line fix mode
                return full_loop(fix_prompt, modelHandler, todo_list, fix_mode=True, backup_name=backup_name, total_cleanup=False, results=results, UI_called=False)
            else:
                # Return to menu with fix prompt
                return False, modelHandler, todo_list, fix_prompt, backup_name
        
        # User declined to fix, or fix mode failed
        if not UI_called:
            # Command-line mode with no fix
            if input("Save changes to extension file? (y/n): ").strip().lower() == 'y':
                action_logger.save_changes_to_extension_file("patches.json", name_of_backup=backup_name)
            action_logger.print_summary(todo_list)
        
        # Return failure
        return False, modelHandler, todo_list, "", backup_name

    else:
        print("Tests passed, continuing...")    
        # Tests passed - success!
        if not UI_called:
            if input("Save changes to extension file? (y/n): ").strip().lower() == 'y':
                action_logger.save_changes_to_extension_file("patches.json", name_of_backup=backup_name)

        print("--------------------------------")
        action_logger.print_summary(todo_list)
        print("--------------------------------")
        
        if not UI_called:
            # Prompt user to see full diffs
            show_diffs = input("\nShow full diffs? (y/n): ").strip().lower()
            if show_diffs == 'y':
                action_logger.print_diffs()
        
        # Return success
        return True, modelHandler, todo_list, "", backup_name

def new_main(prompt: str = None, start_from_base: str = None, patch_to_load: str = None, needs_rebase: bool = True, UI_called=False, provider: str = "GEMINI", model_name: str = "models/gemini-3-flash-preview", gemini_api_key: str = None, openai_api_key: str = None):
    load_dotenv()
    check_integrity()

    handler = BackupHandler("__game_backups")
    backup_name = start_from_base
    
    if patch_to_load and needs_rebase:
        print(f"Loading patch from {patch_to_load}...")
        from coding.non_callable_tools.version_control import VersionControl
        vc = VersionControl()
        success, errors = vc.apply_all_changes(
            needs_rebase=True, 
            path_to_BASE_backup="__game_backups", 
            file_containing_patches=patch_to_load,
            skip_warnings=True
        )
        from BASE_files.BASE_helpers import reload_game_code
        reloaded_setup = reload_game_code()
        if not success:
            print(f"Failed to load patch: {errors}")
            return False, None, None, "", ""
        
        backup_name, _, _ = vc.load_from_extension_file(patch_to_load)
        print(f"Patch loaded successfully. Base backup: {backup_name}")

    elif patch_to_load and not needs_rebase:
        # We assume the UI already loaded the patch, but we still need the backup_name for saving
        from coding.non_callable_tools.version_control import VersionControl
        vc = VersionControl()
        backup_name, _, _ = vc.load_from_extension_file(patch_to_load)
        print(f"Using already loaded patch context. Base backup: {backup_name}")

    elif start_from_base is None:
        # No base specified and no patch to load - create a fresh starting point
        backup_path, backup_name = handler.create_backup("GameFolder") 
        print("Initial backup created at: ", backup_path)

    elif start_from_base and needs_rebase:
        # Rebase to a specific backup
        backup_path, backup_name = handler.restore_backup(start_from_base, target_path="GameFolder")
        print("Restored backup from: ", backup_path)
    
    else:
        # Using existing state or start_from_base was already handled
        print(f"Continuing with current state. Base backup: {backup_name}")
    
    print("Backup name for this session: ", backup_name)

    # start logger
    action_logger.start_session(visual=True)

    # Select the appropriate API key based on provider
    selected_api_key = None
    if provider == "GEMINI" and gemini_api_key:
        selected_api_key = gemini_api_key
    elif provider == "OPENAI" and openai_api_key:
        selected_api_key = openai_api_key

    modelHandler = GenericHandler(thinking_model=True, provider=provider, model_name=model_name, api_key=selected_api_key)
    
    todo_list = TodoList()

    if prompt is None:
        prompt = input("Enter your prompt: ")
    else:
        print("Using prompt: ", prompt)
    
    # Run the main loop (always returns 5 values now)
    success, modelHandler, todo_list, fix_prompt, backup_name = full_loop(
        prompt, 
        modelHandler, 
        todo_list, 
        fix_mode=False, 
        backup_name=backup_name, 
        total_cleanup=True, 
        UI_called=UI_called
    )
    
    # End session on success, or when not called from UI
    if success or not UI_called:
        action_logger.end_session()
    
    # Return values for UI, or just end for command-line
    if UI_called:
        return success, modelHandler, todo_list, fix_prompt, backup_name
    
    """
    REMEMBER
    - Fix mode avoids cleaning up chat history and avoids creating tests
    - When you want to start a completely new task you should both:
        - CLEAN UP chat history or SUMMARIZE chat history
        - Cleanup the Todo List recreating the object to reset
    """
    action_logger.end_session()

if __name__ == "__main__":
    #print(run_all_tests())
    #handler = BackupHandler("__game_backups")
    #handler.restore_backup("20260104161653_GameFolder", target_path="GameFolder")
    #handler.restore_backup("20260104003546_GameFolder", target_path="GameFolder")
    new_main(start_from_base="20260110145521_GameFolder")#start_from_base="20260108141029_GameFolder")#start_from_base="20260104161653_GameFolder")