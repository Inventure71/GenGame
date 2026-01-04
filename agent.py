from time import time
from dotenv import load_dotenv
from coding.non_callable_tools.backup_handling import BackupHandler
from coding.generic_implementation import GenericHandler
from coding.non_callable_tools.gather_context import gather_context_planning, gather_context_coding
from coding.non_callable_tools.todo_list import TodoList
from coding.tools.file_handling import get_tree_directory, read_file, create_file, get_directory
from coding.tools.modify_inline import modify_file_inline
from coding.tools.code_analysis import find_function_usages, get_function_source, list_functions_in_file
from coding.non_callable_tools.action_logger import action_logger
from coding.tools.testing import run_all_tests, parse_test_results
from coding.non_callable_tools.helpers import load_prompt
from coding.non_callable_tools.version_control import VersionControl

#print(get_tree_directory("GameFolder"))
#print(read_file("GameFolder/weapons/GAME_weapon.py"))

error_a = """
Issues to fix:  ['Test: test_projectile_shooting_near_platforms\nFile: mandatory_edge_cases_test.py\nError: Unexpected error: TypeError: \'NoneType\' object is not subscriptable\nTraceback:\nTraceback (most recent call last):\n  File "/Users/inventure71/VSProjects/GenGame/coding/tools/../../BASE_components/BASE_tests.py", line 238, in run_test\n    test_func()\n  File "/Users/inventure71/VSProjects/GenGame/GameFolder/tests/mandatory_edge_cases_test.py", line 125, in test_projectile_shooting_near_platforms\n    proj2 = projs2[0]\nTypeError: \'NoneType\' object is not subscriptable\n\nDuration: 0.001s\n', 'Test: test_marker_to_blast_transition\nFile: orbital_cannon_tests.py\nTraceback:\nTraceback (most recent call last):\n  File "/Users/inventure71/VSProjects/GenGame/coding/tools/../../BASE_components/BASE_tests.py", line 238, in run_test\n    test_func()\n  File "/Users/inventure71/VSProjects/GenGame/GameFolder/tests/orbital_cannon_tests.py", line 119, in test_marker_to_blast_transition\n    assert len(blasts) == 1\nAssertionError\n\nDuration: 0.001s\n', 'Test: test_targeting_laser_tracking\nFile: orbital_cannon_tests.py\nTraceback:\nTraceback (most recent call last):\n  File "/Users/inventure71/VSProjects/GenGame/coding/tools/../../BASE_components/BASE_tests.py", line 238, in run_test\n    test_func()\n  File "/Users/inventure71/VSProjects/GenGame/GameFolder/tests/orbital_cannon_tests.py", line 75, in test_targeting_laser_tracking\n    assert laser.location[0] == pytest.approx(initial_loc[0] + 19.2)\nAssertionError\n\nDuration: 0.000s\n']
"""

def check_integrity():
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

def main():
    load_dotenv()
    check_integrity()
    
    # Initialize the handler
    # thinking_model=False ensures we rely on the prompt's structured reasoning
    # rather than the model's native hidden thinking process for now.
    modelHandler = GenericHandler(thinking_model=True, provider="GEMINI", model_name="models/gemini-3-flash-preview")
    #modelHandler = GenericHandler(thinking_model=True, provider="OPENAI", model_name="gpt-5-mini-2025-08-07")

    handler = BackupHandler("__game_backups")
    # Backup entire directory with subdirectories
    #backup_path = handler.create_backup("/path/to/important_folder")  # recursive=True by default
    # Backup only immediate files in directory
    #backup_path = handler.create_backup("/path/to/folder", recursive=False)
    # Restore backup to original location (overwrites existing)
    #handler.restore_backup("important_folder")
    # Restore to custom location
    #handler.restore_backup("important_folder", "/different/path/important_folder")
    # List available backups
    #backups = handler.list_backups()
    # Delete old backup
    #handler.delete_backup("old_backup")
    was_fixing_issues = False

    backup_path, backup_name = handler.create_backup("GameFolder") 
    print("Backup created at: ", backup_path)
    print("Backup name: ", backup_name)

    print("Starting Logger...")
    action_logger.start_session(visual=True)  # Start tracking actions with visual streaming


    print("Initializing GenGame Autonomous Architect...")
    
    coding_sys_prompt = load_prompt("coding/system_prompts/coding.md")
    planning_sys_prompt = load_prompt("coding/system_prompts/planning.md")

    todo_list = TodoList()

    # Register tools
    planning_tools = [
        todo_list.append_to_todo_list,
        read_file,
        find_function_usages,
        get_function_source,
        list_functions_in_file,
        get_directory,
        # get_tree_directory,  # Already provided in planning context

    ]

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

    print("\n--- GenGame Agent REPL ---")
    print("Type 'exit' or 'quit' to end session.")
    print("--------------------------\n")

    while True:
        try:
            user_input = input("User: ").strip()
        except EOFError:
            break

        if not user_input:
            continue
            
        if user_input.lower() in ['exit', 'quit']:
            print("Exiting...")
            break
        if user_input == "error_a":
            user_input = error_a
            was_fixing_issues = True
            print("Was fixing issues, setting to True, so we don't create tests again")
            print("User input: ", user_input)
            
        # We fist make it plan
        action_logger.start_session(visual=True)  # Start tracking actions with visual streaming
        action_logger.set_todo_list(todo_list) 
        modelHandler.set_tools(planning_tools)
        modelHandler.setup_config("HIGH", planning_sys_prompt, tools=planning_tools)
        modelHandler.clean_chat_history()

        full_prompt = f"""
        Objective: {user_input}
        Starting Context:\n{gather_context_planning()}
        """
        
        print("--------------------------------")
        print("Planning...") # the goal is to create a few tasks to be completed with a deep description
        planning_response = modelHandler.generate_response(
            prompt=full_prompt, 
            use_tools=True, 
            use_history=True
        )
        print(planning_response) 

        print("--------------------------------")
        print("Setting up coding agent...")
        print("------ Summarizing chat history... ------")
        modelHandler.summarize_chat_history(autocleanup=True)

        print("------ Summarized chat history ------")
        modelHandler.set_tools(all_tools)
        modelHandler.setup_config("LOW", coding_sys_prompt, tools=all_tools)
        print("Waiting 5 seconds for the API to be ready...")
        time.sleep(5)
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

            old_full_prompt = (
                f"General Objective: {user_input}\n"
                f"Current Step: {todo_item_str}\n"
                f"Instructions: Complete the current task using your tools. "
                f"Once finished, you MUST call 'complete_task' to proceed."
            )

            full_prompt = f"""TASK FOCUS: Complete ONLY the current step. Ignore all other objectives until this specific task is done.
            Current Task: {todo_item_str}

            Requirements: Use your tools to implement exactly what this task specifies.
            When finished, call 'complete_task' immediately - do not continue to other features.

            Remember: Stay focused on this single task. Do not implement additional features or optimizations beyond what's required.
            
            Starting Context:\n{gather_context_coding()}
            """
            
            current_index = modelHandler.ask_until_task_completed(todo_list, current_index, full_prompt, summarize_at_completion=True)
            print("--------------------------------")

        if not was_fixing_issues:
            print("--------------------------------")
            print("Generating tests...")
            # we add to the todo list the task of creating the tests
            todo_list.append_to_todo_list("Create tests for the newly implemented features", "Create tests for all the newly implemented features in the GameFolder/tests/ directory.")
            current_index = todo_list.index_of_current_task # this will be already set by the append_to_todo_list call
            
            modelHandler.summarize_chat_history(autocleanup=True)
            # First we generate the tests for the custom functions that were implemented
            # We still use the same tools
            modelHandler.setup_config("MEDIUM", load_prompt("coding/system_prompts/testing.md"), tools=all_tools)
            
            # here we make sure that it runs until the todo isn't marked as completed
            all_tasks = todo_list.get_all_tasks()
            full_prompt = (
                f"General Objective: {user_input}\n"
                f"All steps done so far: {all_tasks}\n"
                f"Guide to creating tests: {load_prompt('coding/prompts/GUIDE_Testing.md')}\n"
                f"Instructions: Create the tests for all the features and interactions that were implemented. "
                f"Once finished, you MUST call 'complete_task' to proceed."
            )
            print("Creating tests...")
            current_index = modelHandler.ask_until_task_completed(todo_list, current_index, full_prompt, summarize_at_completion=False)
            print("Tests created (REMEMBER THAT WE DIDN'T SUMMARIZE THE CHAT FOR NOW)")
            print("--------------------------------")

        # Then we give the model the answer to all the tests
        print("Running tests...")
        results = run_all_tests()
        print("Tests results: ", results)

        if input("Save changes to extension file? (y/n): ").strip().lower() == 'y':
            action_logger.save_changes_to_extension_file("patches.json", name_of_backup=backup_name)
        
        issues_to_fix = parse_test_results(results)
        if len(issues_to_fix) > 0:
            print("Tests failed, please fix the issues and run the tests again")
            print("Issues to fix: ", issues_to_fix)
            raise Exception("Tests failed, please fix the issues and run the tests again")
            
        print("Tests passed, continuing...")    
        #gemini.set_tools([run_all_tests])

        # End session and show summary
        action_logger.end_session()
        action_logger.print_summary(todo_list)
        
        # Prompt user to see full diffs
        show_diffs = input("\nShow full diffs? (y/n): ").strip().lower()
        if show_diffs == 'y':
            action_logger.print_diffs()
        
        # The generate_response method (and ask_gemini) already prints 
        # streaming output/thoughts to stdout in the current implementation.
        # So we might not need to print response again if it's already printed.
        # However, let's look at gemini_implementation.py again. 
        # It prints [MODEL]: text. If we print response again, it might duplicate.
        # But generate_response returns the final text.
        
        # Let's check if the implementation prints the final answer.
        # ask_gemini prints parts as they come in.
        
        # If the user wants to see the final accumulated response again cleanly:
        # print(f"\nFinal Response:\n{response}\n") 
        # For now, relying on the streaming output in ask_gemini is probably enough interaction.

def main_manual_repl():
    load_dotenv()
    check_integrity()

    # Use your existing GenericHandler interface
    #modelHandler = GenericHandler(
    #    thinking_model=True,
    #    provider="OPENAI",
    #    model_name="gpt-5-mini-2025-08-07",  # replace with an Ollama model you actually have
    #)
    handler = BackupHandler("__game_backups")
    backup_path, backup_name = handler.create_backup("GameFolder") 
    print("Backup created at: ", backup_path)
    print("Backup name: ", backup_name)

    modelHandler = GenericHandler(
        thinking_model=True,
        provider="GEMINI",
        model_name="models/gemini-3-flash-preview",  # replace with an Ollama model you actually have
    )

    print("Starting Logger...")
    action_logger.start_session(visual=True)

    coding_sys_prompt = "You are a helpful assistant that can answer questions and help with tasks."

    # Non-destructive tools only (from your existing list)
    safe_tools = [
        read_file,
        get_directory,
        get_tree_directory,
        list_functions_in_file,
        find_function_usages,
        get_function_source,
    ]

    writing_tools = [
        create_file,
        modify_file_inline,
    ]

    modelHandler.set_tools(safe_tools)
    modelHandler.setup_config("LOW", coding_sys_prompt, tools=safe_tools)
    modelHandler.clean_chat_history()

    print("\n--- Manual Agent REPL (SAFE tools only) ---")
    print("Commands:")
    print("  /ask <prompt>        -> call model with history + tools")
    print("  /ask_nohist <prompt> -> call model without saving to history")
    print("  /summary             -> summarize since last summary (no cleanup)")
    print("  /summary_clean       -> summarize + autocleanup=True (tests memory compaction)")
    print("  /clear               -> clean_chat_history (tests removal)")
    print("  /history_len         -> print len(chat_history)")
    print("  /run_tests           -> run all tests")
    print("  /t_wt                -> test writing tools")
    print("  /exit")
    print("------------------------------------------\n")

    while True:
        try:
            cmd = input("User: ").strip()
        except EOFError:
            break

        if not cmd:
            continue

        if cmd in ("/exit", "exit", "quit", "/quit"):
            break

        if cmd.startswith("/ask_nohist "):
            prompt = cmd[len("/ask_nohist "):].strip()
            resp = modelHandler.generate_response(
                prompt=prompt,
                use_tools=False,
                use_history=False,  # does not persist
            )
            print("\n[RETURNED]:\n", resp, "\n")
            continue

        if cmd.startswith("/ask "):
            prompt = cmd[len("/ask "):].strip()
            resp = modelHandler.generate_response(
                prompt=prompt,
                use_tools=True,
                use_history=True,   # persists (memory test)
            )
            print("\n[RETURNED]:\n", resp, "\n")
            continue

        if cmd == "/summary":
            s = modelHandler.summarize_chat_history(autocleanup=False)
            print("\n[SUMMARY]:\n", s, "\n")
            continue

        if cmd == "/summary_clean":
            s = modelHandler.summarize_chat_history(autocleanup=True)
            print("\n[SUMMARY + CLEAN]:\n", s, "\n")
            continue

        if cmd == "/clear":
            modelHandler.clean_chat_history()
            print("History cleared.\n")
            continue

        if cmd == "/history_len":
            # Assumes GenericHandler exposes chat_history like your Gemini/OpenAI handlers
            n = len(getattr(modelHandler, "chat_history", []))
            print(f"chat_history length: {n}\n")
            continue

        if cmd.startswith("/t_wt"): # t_wt = test writing tools
            prompt = cmd[len("/t_wt "):].strip()
            # temporary adding the writing tools to the model
            modelHandler.set_tools(safe_tools + writing_tools)
            modelHandler.setup_config("LOW", coding_sys_prompt, tools=safe_tools + writing_tools)
    
            resp = modelHandler.generate_response(
                prompt=prompt,
                use_tools=True,
                use_history=True,   # persists (memory test)
            )
            print("\n[RETURNED]:\n", resp, "\n")
            # removing the writing tools from the model
            modelHandler.set_tools(safe_tools)
            modelHandler.setup_config("LOW", coding_sys_prompt, tools=safe_tools)
            continue

        if cmd == "/run_tests":
            results = run_all_tests()
            #print("Tests results: ", results)
            issues_to_fix = parse_test_results(results)
            if len(issues_to_fix) > 0:
                print("Tests failed, please fix the issues and run the tests again")
                print("Issues to fix: ", issues_to_fix)
                raise Exception("Tests failed, please fix the issues and run the tests again")
            else:
                print("Tests passed, continuing...")
            continue

        print("Unknown command.\n")
    
    for file in action_logger.file_changes:
        print("--------------------------------")
        print(f"Diff for {file}:")
        print(action_logger.get_diff(file))
        print("--------------------------------")
    
    if input("Save changes to extension file? (y/n): ").strip().lower() == 'y':
        action_logger.save_changes_to_extension_file("patches.json", name_of_backup=backup_name)

    action_logger.end_session()
    print("Session ended.")

def main_version_control():
    load_dotenv()
    check_integrity()
    action_logger.start_session(visual=True)
    version_control = VersionControl(action_logger, path_to_security_backup="__TEMP_SECURITY_BACKUP")
    version_control.merge_all_changes(needs_rebase=True, path_to_BASE_backup="__game_backups", file_containing_patches="patches.json")

if __name__ == "__main__":
    
    #print(run_all_tests())
    #handler = BackupHandler("__game_backups")
    #handler.restore_backup("20260104025335_GameFolder", target_path="GameFolder")
    #handler.restore_backup("20260104003546_GameFolder", target_path="GameFolder")
    main()
    #main_manual_repl()
    #main_version_control()
    #print(gather_context_planning())
    #print(gather_context_coding())

#gemini.set_tools(tools)

#print(gemini.generate_response(prompt, use_tools=True, use_history=True))