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
from coding.non_callable_tools.helpers import load_prompt
from coding.non_callable_tools.helpers import check_integrity

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
    time.sleep(2)

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

def full_loop(prompt: str, modelHandler: GenericHandler, todo_list: TodoList, fix_mode: bool, backup_name: str, total_cleanup: bool, results: dict=None, UI_called=False):
    if total_cleanup:
        modelHandler.clean_chat_history()

    plan_feature(prompt, modelHandler, todo_list, fix_mode=fix_mode, results=results)
    implement_feature(modelHandler, todo_list)
    
    if not fix_mode:
        generate_tests(prompt, modelHandler, todo_list)
    else:
        print("Skipping tests generation in fix mode")

    suite = run_all_tests(verbose=False)
    # Convert TestSuite to dict format expected by parse_test_results
    results = {
        "success": suite.all_passed,
        "total_tests": suite.total_tests,
        "passed_tests": suite.passed_tests,
        "failed_tests": suite.failed_tests,
        "duration": suite.total_duration,
        "summary": suite.get_summary(),
        "failures": [
            {
                "test_name": result.test_name,
                "source_file": result.source_file,
                "error_msg": result.error_msg,
                "traceback": result.error_traceback,
                "duration": result.duration
            }
            for result in suite.results if not result.passed
        ]
    }
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
            print("Not cleaning up chat history in fix mode but we are summarizing it again in case last step wasn't summarized")
            modelHandler.summarize_chat_history(autocleanup=True)
            # files involved in issues_to_fix
            prompt = (
                f"## The following tests failed, understand why and fix the issues\n"
                f"{issues_to_fix}\n"
            )
            if not UI_called:
                full_loop(prompt, modelHandler, todo_list, fix_mode=True, backup_name=backup_name, total_cleanup=False, results=results)
            else:
                return False, modelHandler, todo_list, prompt, backup_name
        
        elif fix_mode:
            return False
    
    else:
        print("Tests passed, continuing...")    
        if fix_mode:
            if not UI_called:
                return True
            else:
                return True, modelHandler, todo_list, "", backup_name

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

def new_main(prompt: str = None, start_from_base: str = None, UI_called=False):
    load_dotenv()
    check_integrity()

    handler = BackupHandler("__game_backups")
    if start_from_base is None:
        backup_path, backup_name = handler.create_backup("GameFolder") 
        print("Backup created at: ", backup_path)

    else:
        backup_path, backup_name = handler.restore_backup(start_from_base, target_path="GameFolder")
        print("Restored backup from: ", backup_path)
    
    print("Backup name: ", backup_name)

    # start logger
    action_logger.start_session(visual=True)

    modelHandler = GenericHandler(thinking_model=True, provider="GEMINI", model_name="models/gemini-3-flash-preview")
    
    todo_list = TodoList()

    if prompt is None:
        prompt = input("Enter your prompt: ")
    else:
        print("Using prompt: ", prompt)
    
    if not UI_called:
        full_loop(prompt, modelHandler, todo_list, fix_mode=False, backup_name=backup_name, total_cleanup=True, UI_called=UI_called)

        action_logger.end_session()
    else:
        if UI_called:
            success, modelHandler, todo_list, prompt, backup_name = full_loop(prompt, modelHandler, todo_list, fix_mode=False, backup_name=backup_name, total_cleanup=True, UI_called=UI_called)
        else:
            success, modelHandler, todo_list, prompt = full_loop(prompt, modelHandler, todo_list, fix_mode=False, backup_name=backup_name, total_cleanup=True, UI_called=UI_called)

        if success:
            action_logger.end_session()

        return success, modelHandler, todo_list, prompt, backup_name
    
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
    new_main(start_from_base="20260109000711_GameFolder")#start_from_base="20260108141029_GameFolder")#start_from_base="20260104161653_GameFolder")