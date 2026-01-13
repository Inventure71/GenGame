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
from coding.tools.conflict_resolution import get_all_conflicts, resolve_conflict, set_conflict_todo_tracking, clear_conflict_todo_tracking
from coding.non_callable_tools.todo_list import TodoList

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
