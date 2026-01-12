import math
import time
import hashlib
from typing import List, Dict
from dotenv import load_dotenv
import pygame
from coding.non_callable_tools.backup_handling import BackupHandler
from coding.generic_implementation import GenericHandler
from coding.tools.file_handling import get_tree_directory, read_file, create_file, get_directory
from coding.tools.modify_inline import modify_file_inline
from coding.tools.code_analysis import find_function_usages, get_function_source, list_functions_in_file
from coding.non_callable_tools.action_logger import action_logger
from coding.tools.testing import run_all_tests_tool, parse_test_results
from coding.non_callable_tools.version_control import VersionControl
from coding.non_callable_tools.helpers import check_integrity, load_prompt
from coding.tools.conflict_resolution import get_all_conflicts, resolve_conflict

def main_version_control(file_containing_patches: str = "patches.json"):
    load_dotenv()
    check_integrity()
    action_logger.start_session(visual=True)
    version_control = VersionControl(action_logger, path_to_security_backup="__TEMP_SECURITY_BACKUP")
    result, errors = version_control.apply_all_changes(needs_rebase=True, path_to_BASE_backup="__game_backups", file_containing_patches=file_containing_patches)
    print("\n" * 10)
    if result:
        print("-----    SUCCESS    -----")
        print("All changes applied successfully")
    else:
        print("-----    FAILED    -----")
        print("Some changes failed to apply")
        print(errors)

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
            results = run_all_tests_tool()
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
        action_logger.save_changes_to_extension_file("patches.json", name_of_backup=backup_name, base_backups_root="__game_backups")

    action_logger.end_session()
    print("Session ended.")

def auto_fix_conflicts(path_to_problematic_patch: str, patch_paths: List[str] = None, base_backup: str = None):
    """
    Auto-fix conflicts in a merged patch, with caching support.

    Args:
        path_to_problematic_patch: Path to the patch file with conflicts
        patch_paths: List of original patch files (for caching)
        base_backup: Base backup name (for caching)
    """
    from coding.tools.conflict_resolution import clear_resolution_tracker

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
            print(f"✅ All conflicts resolved using cache ({cached_resolutions_applied} applied)")
            return

    if cached_resolutions_applied > 0:
        print(f"Cache resolved {cached_resolutions_applied} conflicts, {sum(len(c) for c in get_all_conflicts(path_to_problematic_patch).values())} remaining")
    else:
        print("No cached resolutions available, proceeding with LLM resolution...")

    load_dotenv()
    check_integrity()
    action_logger.start_session(visual=True)
    print("Waiting 5 seconds to start...")
    time.sleep(5)

    modelHandler = GenericHandler(
        thinking_model=True,
        provider="GEMINI",
        model_name="models/gemini-3-flash-preview",
    )
    tools = [
        # add the tool to fix the conflict
        resolve_conflict,    
        read_file,
    ]

    # Load the dedicated conflict resolution system prompt
    fix_conflicts_sys_prompt = load_prompt("coding/system_prompts/solve_conflicts.md", include_general_context=False)

    modelHandler.set_tools(tools)
    modelHandler.setup_config("LOW", fix_conflicts_sys_prompt, tools=tools)

    max_conflicts_per_request = 10

    for file_path, conflicts in conflicts_by_file.items():
        print(f"File: {file_path}")
        print("Cleaning chat history for this file...")
        modelHandler.clean_chat_history()

        # IMPORTANT: Process conflicts in REVERSE order (highest conflict_num first)
        # This prevents renumbering issues when resolving multiple conflicts
        conflicts_reversed = sorted(conflicts, key=lambda c: c['conflict_num'], reverse=True)

        len_conflicts = len(conflicts_reversed)
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
            conflicts_block = conflicts_reversed[start_idx:end_idx]
            
            # Format conflicts for the prompt in a readable way
            conflicts_formatted = []
            for conflict in conflicts_block:
                conflicts_formatted.append({
                    'conflict_num': conflict['conflict_num'],
                    'option_a': conflict['option_a'],
                    'option_b': conflict['option_b']
                })
                print(f"Conflict #{conflict['conflict_num']}:")
                print(f"  Option A: {conflict['option_a']}")
                print(f"  Option B: {conflict['option_b']}")
            
            # Build prompt with ALL required info including patch_path
            prompt = (
                f"## Patch file: `{path_to_problematic_patch}`\n"
                f"## File with conflicts: `{file_path}`\n\n"
                f"### Conflicts to resolve (resolve from HIGHEST conflict_num to LOWEST):\n"
                f"{conflicts_formatted}\n\n"
                f"Resolve ALL conflicts using the `resolve_conflict` tool. "
                f"Remember: patch_path='{path_to_problematic_patch}', file_path='{file_path}'"
            )
            print("Sending prompt to model...")
            resp = modelHandler.generate_response(
                prompt=prompt,
                use_tools=True,
                use_history=True,
            )
            print("\n[RETURNED]:\n", resp, "\n")
        
    print("Completed merge handling, checking for conflicts again...")
    remaining_conflicts = get_all_conflicts(path_to_problematic_patch)

    if len(remaining_conflicts) > 0:
        print("Conflicts still exist, please fix them manually")
        print("Conflicts: ", remaining_conflicts)
        raise Exception("Conflicts still exist, please fix them manually")
    else:
        print("No conflicts found, continuing...")

        # Cache the successful resolutions if we have the required information
        if base_backup and cached_resolutions_applied == 0:
            # Only cache if we actually did LLM resolution (not just applied cache)
            _cache_successful_resolutions(path_to_problematic_patch, base_backup, conflicts_by_file)


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
        print(f"✅ Cached {cached_count} LLM resolutions for future reuse")
    else:
        print("No resolutions to cache")

def main_version_control_interactive():
    load_dotenv()
    check_integrity()
    action_logger.start_session(visual=True)
    
    vc = VersionControl()

    # Merge two patches
    success, result = vc.merge_patches(
        base_backup_path="__game_backups",      # Folder containing the backup
        patch_a_path="__patches/RainingCats.json",
        patch_b_path="__patches/kamehameha.json",
        output_path="merged_patch.json"         # Optional, defaults to "merged_patch.json"
    )

    if success:
        print(f"Merged successfully: {result}")
    else:
        print(f"Merge issues: {result}")
        # If there were conflicts, show them
        print(get_all_conflicts("merged_patch.json"))
        
        #vc.resolve_conflicts_interactive("merged_patch.json")
    
    action_logger.end_session()



if __name__ == "__main__":
    print(run_all_tests_tool())
    #print(load_prompt("coding/system_prompts/fix_agent.md"))
    #handler = BackupHandler("__game_backups")
    #print(handler.compute_directory_hash("GameFolder"))

    #main_version_control_interactive()
    #auto_fix_conflicts("merged_patch.json")
    #main_version_control(file_containing_patches="merged_patch_err.json")

    #print(get_file_outline("GameFolder/weapons/GAME_weapon.py"))
    #results = run_all_tests()
    #print("Results: ", results)
    #print("--------------------------------")
    #issues_to_fix = parse_test_results(results)
    #print(issues_to_fix)
    #print("--------------------------------")
    #error_context = gather_context_fix(results)
    #print("Error context: ", error_context)
    #handler = BackupHandler("__game_backups")
    #handler.restore_backup("20260104025335_GameFolder", target_path="GameFolder")
    #handler.restore_backup("20260104003546_GameFolder", target_path="GameFolder")
    #main_manual_repl()
    #main_version_control(file_containing_patches="__server_patches/merged_patch.json")
    #main_version_control(file_containing_patches="__patches/water.json")
    #print(gather_context_planning())
    #print(gather_context_coding())
