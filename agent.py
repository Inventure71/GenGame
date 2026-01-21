import time
import math
import os
from typing import List, Dict
from dotenv import load_dotenv
from BASE_files.BASE_helpers import load_settings
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
from coding.tools.conflict_resolution import get_all_conflicts, resolve_conflict

def get_model_handler(settings: dict):
    return GenericHandler(
        thinking_model=True,
        provider=settings["selected_provider"],
        model_name=settings["model_name"],
        api_key=settings["api_key"]
    )

def auto_fix_conflicts(settings: dict, path_to_problematic_patch: str, patch_paths: List[str] = None, base_backup: str = None):
    """
    Auto-fix conflicts in a merged patch, with caching support.

    Args:
        path_to_problematic_patch: Path to the patch file with conflicts
        patch_paths: List of original patch files (for caching)
        base_backup: Base backup name (for caching)
    """
    from coding.tools.conflict_resolution import clear_resolution_tracker
    import hashlib
    import json

    # Phase 0: Check for cached merged patch based on input patches
    if patch_paths:
        print("Checking for cached merged patch...")
        try:
            # Create a combined hash of all input patches
            combined_content = ""
            for patch_path in sorted(patch_paths):  # Sort for consistent hashing
                if os.path.exists(patch_path):
                    with open(patch_path, 'r') as f:
                        combined_content += f.read()

            if combined_content:
                combined_hash = hashlib.sha256(combined_content.encode()).hexdigest()
                from coding.non_callable_tools.simple_conflict_cache import get_conflict_cache
                cache = get_conflict_cache()

                cached_patch = cache.get_merged_patch(combined_hash)
                if cached_patch:
                    print(f"[success] Found cached merged patch for this combination. Using cached result.")
                    # Replace the problematic patch with the cached resolved one
                    with open(path_to_problematic_patch, 'w') as f:
                        json.dump(cached_patch, f, indent=2)
                    print(f"Applied cached merged patch. Skipping resolution process.")
                    return

        except Exception as e:
            print(f"Could not check merged patch cache: {e}")

    # Check if we've already resolved conflicts for this patch before
    # Check if ALL conflicts can be resolved from individual conflict cache
    print("Checking if all conflicts can be resolved from cache...")
    from coding.non_callable_tools.simple_conflict_cache import get_conflict_cache

    # First, check if we have cached resolutions for ALL conflicts
    conflicts = get_all_conflicts(path_to_problematic_patch)
    cache = get_conflict_cache()
    all_conflicts_cacheable = True
    total_conflicts = 0

    for file_path, file_conflicts in conflicts.items():
        for conflict in file_conflicts:
            total_conflicts += 1
            conflict_hash = cache.get_conflict_hash(conflict["option_a"], conflict["option_b"])
            cached_resolution = cache.get_resolution(conflict_hash, base_backup)
            if not cached_resolution:
                all_conflicts_cacheable = False
                break
        if not all_conflicts_cacheable:
            break

    if all_conflicts_cacheable and total_conflicts > 0:
        print(f"All {total_conflicts} conflicts have cached resolutions. Applying them...")
        # Apply all cached resolutions
        cached_resolutions_applied = 0
        from coding.non_callable_tools.simple_conflict_cache import try_apply_cached_conflicts
        cached_resolutions_applied = try_apply_cached_conflicts(path_to_problematic_patch, base_backup)

        # Verify all were resolved
        remaining_conflicts = get_all_conflicts(path_to_problematic_patch)
        total_remaining = sum(len(c) for c in remaining_conflicts.values())

        if total_remaining == 0:
            print(f"Successfully resolved all conflicts using cache ({cached_resolutions_applied} applied). Skipping LLM resolution.")
            return
        else:
            print(f"Cache application incomplete: {cached_resolutions_applied} applied, {total_remaining} remaining. Proceeding with LLM resolution.")
    else:
        print(f"Not all conflicts have cached resolutions ({'none found' if total_conflicts == 0 else 'some missing'}). Proceeding with LLM resolution.")

    # Calculate patch hash for caching the successful resolution later
    patch_hash = None
    try:
        with open(path_to_problematic_patch, 'r') as f:
            patch_content = f.read()
        patch_hash = hashlib.sha256(patch_content.encode()).hexdigest()
    except Exception as e:
        print(f"Could not calculate patch hash: {e}")

    conflicts_by_file = get_all_conflicts(path_to_problematic_patch)
    print(f"Found conflicts in {len(conflicts_by_file)} file(s)")

    if len(conflicts_by_file) == 0:
        print("No conflicts found, continuing...")
        return

    # Clear resolution tracker for new session
    clear_resolution_tracker()

    # Try to apply cached resolutions if we have patch information
    cached_resolutions_applied = 0
    if base_backup:
        from coding.non_callable_tools.simple_conflict_cache import try_apply_cached_conflicts

        cached_resolutions_applied = try_apply_cached_conflicts(path_to_problematic_patch, base_backup)

        # Check if all conflicts were resolved by cache
        remaining_conflicts = get_all_conflicts(path_to_problematic_patch)
        if len(remaining_conflicts) == 0:
            print(f"All conflicts resolved using cache ({cached_resolutions_applied} applied)")
            return

    if cached_resolutions_applied > 0:
        print(f"Cache resolved {cached_resolutions_applied} conflicts, {sum(len(c) for c in get_all_conflicts(path_to_problematic_patch).values())} remaining")
    else:
        print("No cached resolutions available, proceeding with LLM resolution...")

    load_dotenv()
    check_integrity()
    action_logger.start_session(visual=True)

    # We create it here so we don't have to import the class in the other file 
    modelHandler = get_model_handler(settings)

    # Load the dedicated conflict resolution system prompt
    fix_conflicts_sys_prompt = load_prompt("coding/system_prompts/solve_conflicts.md", include_general_context=False)

    max_conflicts_per_request = 100

    # Phase 1: Resolve all conflicts for all files (without applying)
    print("Phase 1: Resolving conflicts for all files...")
    for file_path, conflicts in conflicts_by_file.items():
        print(f"File: {file_path}")
        print(f"Processing {len(conflicts)} conflicts...")
        print("Cleaning chat history for this file...")
        modelHandler.clean_chat_history()

        len_conflicts = len(conflicts)
        if len_conflicts > max_conflicts_per_request:
            print("A lot of conflicts, splitting them into batches of 10")
            num_blocks = math.ceil(len_conflicts / max_conflicts_per_request)
            print(f"Number of blocks: {num_blocks} because we have {len_conflicts} conflicts and we can handle {max_conflicts_per_request} at once")
        else:
            num_blocks = 1
            print("Less than max conflicts per request, so we can handle all in one call")

        for i in range(num_blocks):
            start_idx = i * max_conflicts_per_request
            end_idx = min(start_idx + max_conflicts_per_request, len_conflicts)
            conflicts_block = conflicts[start_idx:end_idx]

            print(f"Processing batch {i+1}/{num_blocks}: conflicts {start_idx+1}-{end_idx}")

            # Create todo items for THIS batch's conflicts
            todo_list = TodoList()
            conflict_to_todo_map = {}
            for j, conflict in enumerate(conflicts_block):
                conflict_str = (
                    f"File: {file_path}\n"
                    f"Patch: {path_to_problematic_patch}\n"
                    f"Conflict #{conflict['conflict_num']}\n"
                    f"Option A: {conflict['option_a']}\n"
                    f"Option B: {conflict['option_b']}\n"
                    f"Choose 'a', 'b' or 'manual' resolution"
                )
                todo_list.append_to_todo_list(
                    f"Resolve conflict #{conflict['conflict_num']}",
                    conflict_str
                )
                conflict_to_todo_map[conflict['conflict_num']] = j  # Map conflict_num to todo index

            # Set up global todo tracking for this batch
            from coding.tools.conflict_resolution import set_conflict_todo_tracking
            set_conflict_todo_tracking(todo_list, conflict_to_todo_map)

            # Set up tools for the model
            tools = [
                resolve_conflict,
                read_file,
            ]
            modelHandler.set_tools(tools)
            modelHandler.setup_config("LOW", fix_conflicts_sys_prompt, tools=tools)

            # Get full todo list for context
            all_tasks = todo_list.get_all_tasks()

            print("--------------------------------")
            print("ALL TASKS:")
            print(all_tasks)
            print("--------------------------------")

            # Try to resolve conflicts in this batch (with retry if needed)
            max_attempts = 10
            for attempt in range(max_attempts):
                print(f"Batch {i+1}/{num_blocks} - Attempt {attempt + 1}/{max_attempts}")

                # Enable deferred application for this attempt
                from coding.tools.conflict_resolution import _defer_application, _pending_resolutions
                _defer_application = True
                _pending_resolutions.clear()

                # Send JUST the todo list string as prompt
                prompt = (
                    "You are merging two patches that both add valuable features. Resolve ALL conflicts in the following todo list:\n\n"
                    f"{all_tasks}\n\n"
                    "CRITICAL: When using 'manual' resolution, ensure PERFECT indentation - Python syntax depends on whitespace!\n"
                    "Fix as many as possible using parallel tool calls, the least turns it takes you to finish the better."
                )

                print(f"Sending todo list for batch {i+1}...")
                resp = modelHandler.generate_response(
                    prompt=prompt,
                    use_tools=True,
                    use_history=True,
                )
                print(f"\n[MODEL RESPONSE for batch {i+1}, attempt {attempt + 1}]:\n", resp, "\n")

                # Apply all collected resolutions in reverse conflict number order
                _pending_resolutions.sort(key=lambda x: x['conflict_num'], reverse=True)
                _defer_application = False

                print(f"Applying {len(_pending_resolutions)} resolutions from attempt {attempt + 1}...")
                for resolution in _pending_resolutions:
                    result = resolve_conflict(**resolution)  # This will auto-complete todos
                    print(f"Applied: {result}")

                # Check if all conflicts in this batch are resolved
                completed_count = sum(1 for task in todo_list.todo_list if task.completed)
                total_count = len(todo_list.todo_list)

                if completed_count == total_count:
                    print(f"[success] Batch {i+1} completed! ({completed_count}/{total_count} conflicts resolved)")
                    break
                else:
                    print(f"Batch {i+1} incomplete: {completed_count}/{total_count} conflicts resolved")
                    if attempt < max_attempts - 1:
                        print("Cleaning chat history and retrying...")
                        modelHandler.clean_chat_history()
                        # Update todo list to show progress
                        all_tasks = todo_list.get_all_tasks()
                    else:
                        print(f"[error] Batch {i+1} failed after {max_attempts} attempts")

            print("Completed batch {i+1}")
            # Clear tracking after each batch
            from coding.tools.conflict_resolution import clear_conflict_todo_tracking
            clear_conflict_todo_tracking()

        print(f"[success] Completed conflict resolution for {file_path}")

    # Phase 2: Apply the entire resolved patch once (in special mode that doesn't revert)
    print("🔄 Phase 2: Applying the entire resolved patch...")
    from coding.non_callable_tools.version_control import VersionControl
    vc = VersionControl()

    try:
        success, success_count, total_changes, errors = vc.apply_patches(path_to_problematic_patch, keep_changes_on_failure=True)
        print(f"Applied {success_count}/{total_changes} changes")
        if errors:
            print(f"Errors encountered: {errors}")
        print("[success] Patch application completed (kept changes even if some failed)")

        # Check if patch applied completely successfully (no errors)
        patch_applied_cleanly = (len(errors) == 0 and success_count == total_changes)

    except Exception as e:
        print(f"[error] Error applying resolved patch: {e}")
        raise

    # Phase 3: Verify each affected file individually (skip if patch applied cleanly)
    if patch_applied_cleanly:
        print("[success] Patch applied without any errors. Skipping verification phase.")
    else:
        print("🔍 Phase 3: Verifying each affected file individually...")
        for file_path in conflicts_by_file.keys():
            print(f"🔍 Starting comprehensive verification of applied file: {file_path}...")

            modelHandler.clean_chat_history()
            todo_list_verification = TodoList()
            todo_list_verification.append_to_todo_list(
                f"Verify and fix applied file: {file_path}",
                f"Perform comprehensive verification of the applied file {file_path}. This file has been "
                f"modified by applying the resolved merge patch. Check for syntax errors, logical issues, "
                f"merge artifacts, and any other problems. Make corrections as needed using modify_file_inline. "
                f"Continue working until you are 100% confident the file is correct and ready for production."
            )
            current_index = todo_list_verification.index_of_current_task

            tools = [
                read_file,
                modify_file_inline,
                todo_list_verification.complete_task,
            ]
            verify_file_sys_prompt = load_prompt("coding/system_prompts/verify_file.md", include_general_context=False)
            modelHandler.set_tools(tools)
            modelHandler.setup_config("LOW", verify_file_sys_prompt, tools=tools)

            full_prompt = (
                f"## Applied File to Verify: {file_path}\n\n"
                f"This file has been modified by applying a resolved merge patch. You need to perform comprehensive "
                f"verification to ensure the result is correct.\n\n"
                f"**Current applied file content:**\n"
                f"```\n"
                f"{read_file(file_path)}\n"
                f"```\n\n"
                f"**Important:** The file content above is the CURRENT, UP-TO-DATE version after patch application. "
                f"Analyze this content for issues rather than reading the file again."
            )
            modelHandler.ask_until_task_completed_V2(todo_list_verification, current_index, full_prompt)
            modelHandler.clean_chat_history()

            print(f"[success] Completed verification of {file_path}")

    # Phase 4: Replace original merged patch with final verified version
    # Use the base_backup parameter passed to the function (don't overwrite it)
    print("📝 Phase 4: Replacing original merged patch with final verified version...")
    if base_backup:
        # Replace the original problematic patch file with the resolved version
        final_patch_path = path_to_problematic_patch

        success = vc.save_to_extension_file(final_patch_path, base_backup)
        if success:
            print(f"[success] Successfully replaced original patch with verified version: {final_patch_path}")
            print("Original merged patch now contains all resolved conflicts and verification fixes")
        else:
            print("[error] Failed to create final verified patch")
    else:
        print("[warning]  No base backup provided, skipping patch replacement")

    # Phase 5: Restore to base game state
    print("🏠 Phase 5: Restoring to base game state...")
    if base_backup:
        try:
            from coding.non_callable_tools.backup_handling import BackupHandler
            base_backup_handler = BackupHandler("__game_backups")
            base_backup_handler.restore_backup(base_backup, target_path="GameFolder")
            print(f"[success] Successfully restored to base game state: {base_backup}")
        except Exception as e:
            print(f"[error] Failed to restore to base game state: {e}")
    else:
        print("[warning]  No base backup provided, cannot restore to base state")

    print("Completed merge handling, checking for conflicts again...")
    remaining_conflicts = get_all_conflicts(path_to_problematic_patch)

    if len(remaining_conflicts) > 0:
        print("Conflicts still exist, please fix them manually")
        print("Conflicts: ", remaining_conflicts)
        raise Exception("Conflicts still exist, please fix them manually")
    else:
        print("No conflicts found, continuing...")

        # Cache the successful merged patch for future reuse
        if patch_paths:
            try:
                combined_content = ""
                for patch_path in sorted(patch_paths):
                    if os.path.exists(patch_path):
                        with open(patch_path, 'r') as f:
                            combined_content += f.read()

                if combined_content:
                    combined_hash = hashlib.sha256(combined_content.encode()).hexdigest()
                    # Load the final resolved patch
                    with open(path_to_problematic_patch, 'r') as f:
                        final_patch = json.load(f)

                    cache.store_merged_patch(combined_hash, final_patch)
                    print(f"[success] Cached final merged patch for future reuse")
            except Exception as e:
                print(f"[warning]  Could not cache merged patch: {e}")

        # Cache the successful resolutions if we have the required information
        # Cache LLM resolutions regardless of whether some cached resolutions were also applied
        # This ensures we learn from successful resolutions even when some cached ones failed
        if base_backup:
            _cache_successful_resolutions(path_to_problematic_patch, base_backup, conflicts_by_file)

        # Patch-level caching removed - relying on individual conflict caching instead

def _cache_successful_resolutions(patch_path: str, base_backup: str, original_conflicts: Dict[str, List[Dict]]):
    """
    Cache the resolutions that were successfully applied to resolve conflicts.
    Uses the tracked resolutions from the LLM interaction.
    """
    from coding.non_callable_tools.simple_conflict_cache import get_conflict_cache
    from coding.tools.conflict_resolution import get_resolution_tracker

    cache = get_conflict_cache()
    tracker = get_resolution_tracker()

    cached_count = 0
    for file_path, conflicts in original_conflicts.items():
        for conflict in conflicts:
            conflict_hash = cache.get_conflict_hash(conflict["option_a"], conflict["option_b"])

            # Get the actual resolution that was applied
            key = f"{file_path}:{conflict['conflict_num']}"
            resolution = tracker.get(key)

            if resolution:
                cache.store_resolution(conflict_hash, base_backup, resolution)
                cached_count += 1

    if cached_count > 0:
        print(f"[success] Cached {cached_count} LLM resolutions for future reuse")
    else:
        print("No resolutions to cache")

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
        print("------ Cleaning up chat history after planning and before implementing ------")
        modelHandler.clean_chat_history()
        #modelHandler.summarize_chat_history(autocleanup=True)
        #print("------ Summarized chat history ------")

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

        all_tasks = todo_list.get_all_tasks(until_index=current_index-1)
        
        full_prompt = (
            f"## All Tasks so far\n"
            f"{all_tasks}\n"
            f"## Current Task\n"
            f"{todo_item_str}\n"
            f"## Instructions\n"
            f"1. Implement exactly what this task specifies\n"
            f"2. Call `complete_task(summary=summary_of_the_task)` when done. Summary must be at least 150 characters of technical details.\n"
            f"3. Do NOT implement features beyond this task\n"
            f"{gather_context_coding()}\n"
        )
            
        current_index = modelHandler.ask_until_task_completed_V2(todo_list, current_index, full_prompt)
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

    if len(modelHandler.chat_history) > 0:
        print("------ Cleaning up chat history after planning and before generating tests ------")
        modelHandler.clean_chat_history()
        #modelHandler.summarize_chat_history(autocleanup=True)
        #print("------ Summarized chat history ------")
    else:
        print("------ STRANGE No chat history to clean up STRANGE ------")

    # First we generate the tests for the custom functions that were implemented
    # We still use the same tools
    modelHandler.set_tools(all_tools)
    modelHandler.setup_config("MEDIUM", load_prompt("coding/system_prompts/testing.md"), tools=all_tools)
        
    # here we make sure that it runs until the todo isn't marked as completed
    all_tasks = todo_list.get_all_tasks(until_index=current_index-1)
    current_task = todo_list.get_current_task()
    full_prompt = (
        f"General Objective: {prompt}\n"
        f"All steps done so far: {all_tasks}\n"
        f"Current task: {current_task}\n"
        f"{gather_context_testing()}\n"
        f"Instructions: Create the tests for all the features and interactions that were implemented. "
        f"Once finished, you MUST call 'complete_task(summary=summary_of_the_task)' to proceed. Summary must be at least 150 characters of technical details."
    )
    print("Creating tests...")
    current_index = modelHandler.ask_until_task_completed_V2(todo_list, current_index, full_prompt)
    print("Tests created")
    print("--------------------------------")

def fix_system(prompt: str, modelHandler: GenericHandler, results: dict):
    if len(modelHandler.chat_history) > 0:
        print("------ Cleaning up chat history after planning and before fixing ------")
        modelHandler.clean_chat_history()
        #modelHandler.summarize_chat_history(autocleanup=True)
        #print("------ Summarized chat history ------")
    else:
        print("------ STRANGE No chat history to clean up STRANGE ------")

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
        f"Current task: {todo_list.get_current_task()}\n"
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
    
    modelHandler.ask_until_task_completed_V2(todo_list, current_index, full_prompt)
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
            results = run_all_tests_tool(explanation="Initial test run before fix cycle")
        todo_list = fix_system(prompt, modelHandler, results)

    results = run_all_tests_tool(explanation="Final test run after implementation/fix cycle")
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

def start_complete_agent_session(prompt: str = None, start_from_base: str = None, patch_to_load: str = None, needs_rebase: bool = True, UI_called=False, settings: dict = None):
    if settings is None:
        print("WARNING: No settings provided, returning False")
        return False, None, None, "", ""

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
    modelHandler = get_model_handler(settings)
    
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
    start_complete_agent_session(start_from_base="20260110145521_GameFolder")#start_from_base="20260108141029_GameFolder")#start_from_base="20260104161653_GameFolder")