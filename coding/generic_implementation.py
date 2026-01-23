from typing import Dict, Any
from coding.non_callable_tools.helpers import load_prompt
from coding.handlers.gemini_handler import GeminiHandler
from coding.handlers.openai_handler import OpenAIHandler
from coding.non_callable_tools.todo_list import TodoList
from coding.standardized_types import StandardizedResponse, StandardizedToolCall, StandardizedToolResult
from google.genai import types

from coding.non_callable_tools.action_logger import action_logger

class GenericHandler:
    def __init__(self, thinking_model, model_name: str = "models/gemini-3-flash-preview", provider: str = "GEMINI", api_key: str = None):
        if provider == "GEMINI":
            self.client = GeminiHandler(thinking_model=thinking_model, model_name=model_name, api_key=api_key)
        elif provider == "OPENAI":
            self.client = OpenAIHandler(thinking_model=thinking_model, model_name=model_name, api_key=api_key)
        elif provider == "OLLAMA":
            self.client = OpenAIHandler(thinking_model=thinking_model, model_name=model_name, force_url="http://localhost:11434/v1")
        else:
            raise ValueError(f"Invalid provider: {provider}")

        self.thinking_model = thinking_model
        self.model_name = model_name

        self.max_iterations_safety_cutoff = 10

        # Both the chat_history and full_history are stored by deafult in the starting client schema
        self.chat_history = []       # Main history (tool calls + text, NO thoughts, NO tool outputs)
        self.full_history = []       # Debug history (everything if needed)
    
        self.summary_history = []          # List of all task summaries in chronological order
        self.last_summary_index = 0       # Index in chat_history where last summary was added 

        self.available_tools = [] # list of functions that needs to be converted to the client schema, using the fixed explanations

        self.setup_config()

    def convert_chat_history_to_client_schema(self, chat_history: list, from_client, to_client): # es from_clinet = geminihandler reference
        new_history = []
        #TODO: Implement this, It should get the entire chat_history and convert from one type to the other
        for item in chat_history:
            role, decomposed_block_list = from_client.convert_from_client_schema_to_text(item)
            new_history.append(to_client.convert_to_client_schema(role, decomposed_block_list))

        return new_history

    def set_tools(self, tools: list):
        self.client.set_tools(tools)
        self.available_tools = tools

    def setup_config(self, thinking_level: str = "MEDIUM", system_instruction: str = None, tools: list = None):
        self.client.setup_config(thinking_level=thinking_level, system_instruction=system_instruction, tools=tools)
    
    def clean_chat_history(self):
        # complete cleanup of all histories
        self.chat_history = []
        self.summary_history = []
        self.full_history = []
        self.last_summary_index = 0
    
    def filter_chat_history(self, most_recent_chat: list):
        return self.client.filter_chat_history(most_recent_chat)

    def summarize_chat_history(self, autocleanup: bool = False):
        """
        Progressively summarizes only the work done since the last summary.
        Maintains a chain of summaries for better context preservation.
        """
        # We ignore the first item in the chat_history because it is the first user prompt that normally is really big
        # Also we want to summarize the things done by the agent not the user instructions
        # We summarize based on the chat_history which now contains:
        # User prompts, Model Text, Tool Calls (sans outputs, sans thoughts).
        
        start_index = self.last_summary_index + 1
        most_recent_chat = self.chat_history[start_index:]
        most_recent_chat = self.filter_chat_history(most_recent_chat) # this will already be in the correct client format

        if not most_recent_chat:
            # No new content to summarize
            print(f"DEBUG: No new work to summarize, REALLY REALLY STRANGE!!!")
            return "No new work to summarize."

        #summarize_system = "You are a helpful assistant that summarizes technical work done in previous conversations."
        #self.client.setup_config(thinking_level="LOW", system_instruction=summarize_system, tools=None)
        
        prompt = load_prompt("coding/prompts/summarize_history.md", include_general_context=False)
        response = self.generate_response(prompt, use_tools=False, use_history=True, chat_history_to_update=most_recent_chat)

        summary_entry = f"TASK SUMMARY ({len(self.summary_history) + 1}):\n{response}"
        self.summary_history.append(summary_entry)

        if autocleanup:
            # we just clean the memory and then add the summaries to the empty chat
            self.chat_history = []
            self.chat_history.append(self.client.convert_to_client_schema(role="user", content="Summarize what has been accomplished so far."))
            combined_summary = "\n\n".join(self.summary_history)
            self.chat_history.append(self.client.convert_to_client_schema(role="assistant", content=combined_summary))
            
            #for summary in self.summary_history:
            #    self.chat_history.append(self.client.convert_to_client_schema(role="user", content="Summarize what has been accomplished so far."))
            #    # Use "assistant" role for OpenAI compatibility (Gemini accepts "model" too)
            #    self.chat_history.append(self.client.convert_to_client_schema(role="assistant", content=summary))
            
        self.last_summary_index = len(self.chat_history) - 1
        return response

    def generate_response(self, prompt: str, use_tools: bool = False, use_history: bool = False, chat_history_to_update: list = None) -> str:
        # 1. Create a TEMPORARY history for this specific turn
        # check if the prompt is already an history item, if so, use it as is
        user_content = self.client.convert_to_client_schema(role="user", content=prompt)
        
        # Determine which history to use and update
        if use_history:
            if chat_history_to_update is None:
                chat_history_to_update = self.chat_history
            # Append to permanent history immediately
            chat_history_to_update.append(user_content)
            # Use chat_history as the base context
            turn_history = list(chat_history_to_update) 
        else:
            turn_history = [user_content]

        if use_tools:
            active_config = self.client.get_config()
        else:
            active_config = self.client.temporary_no_tools_config()
            
        # 2. Get the answer        
        final_text = self.ask_model(turn_history, active_config, history_to_update=chat_history_to_update)
        #final_text = self.client.ask_model(turn_history, active_config, history_to_update=chat_history_to_update)
        
        return final_text

    def ask_until_task_completed_V2(self, todo_list: TodoList, current_index: int, full_prompt: str) -> str:
        iteration_count = 0
        while iteration_count < self.max_iterations_safety_cutoff:
            if iteration_count > 0:
                full_prompt = "Continue the task until it is completed. Ensure you have addressed all requirements of the current task step."
            iteration_count += 1
            print("Iteration: ", iteration_count)

            # We use use_history=True to maintain context across the session
            response = self.generate_response(
                prompt=full_prompt, 
                use_tools=True, 
                use_history=True
            )

            temp_index = todo_list.index_of_current_task
            if temp_index == -1:
                print("Agent has completed all tasks")
                return -1
            elif temp_index != current_index:
                print("Agent has completed a task")
                print("The model should have called complete_task with the summary of the task so we clean up the chat history")
                self.clean_chat_history()
                return temp_index
            else:
                print("Agent has not completed the task yet")

    def _compose_message(self, main_message: str, append_warning_str: str = "", item_index: int = -1, last_index_plus_one: int = -1) -> str:
        if append_warning_str and item_index == (last_index_plus_one - 1):
            return f"{main_message}\n{append_warning_str}" # we only append the warning if it is the last item
        return main_message

    def ask_model(self, history: list, config: types.GenerateContentConfig, history_to_update: list = None, auto_nudge: int = 2, auto_truncate_history: int = 0) -> str:
        """
        Generalized ask_model that works with any provider through BaseHandler interface.
        The common logic is here, provider-specific details are handled by the client.
        NOTE: To disable auto nudging, set auto_nudge to -1.
        NOTE: To disable auto truncation of history, set auto_truncate_history to 0.
        """
        turns = 0
        max_turns = 30  # Safety cutoff
        stop_loop = False
        number_of_tools_used_last_turn = 0
        
        # Local list to track the conversation turn including tool outputs 
        # so the model can actually see the results of its actions during THIS turn.
        # But we will NOT append the tool outputs to self.chat_history.
        current_turn_log = [] 
        current_turn_log_tests = []
        
        while turns < max_turns and not stop_loop:
            turns += 1
            result_run_tests_tool = None
            explanation_run_tests_tool = None
            print(f"DEBUG: Turn {turns}", flush=True)

            # We use history + current_turn_log for the API call (DEPRECATED)
            # This ensures the model sees the tool outputs for the current interaction loop (DEPRECATED)
            api_history = history + current_turn_log

            # 1. Make API call (provider-specific)
            try:
                print("STARTING API CALL")
                response = self.client.make_api_call(api_history, config)
                print("API CALL COMPLETED")
            except Exception as e:
                print(f"API call failed: {e}")
                raise e
            
            # 2. Parse response into standardized format (provider-specific → standardized)
            standardized_response = self.client.parse_response(response)
            
            # 3. Display thoughts and text content (standardized)
            for thought in standardized_response.thoughts:
                print(f"\n[THOUGHT]: {thought}", flush=True)
                action_logger.log_thinking(thought, chat_history=api_history)
            
            for text in standardized_response.text_parts:
                print(f"\n[MODEL]: {text}", flush=True)
                action_logger.log_model_text(text, chat_history=api_history)

            # 4. Handle History (provider-specific logic)
            self.client.add_response_to_history(response, current_turn_log, history_to_update)

            # 5. Process Tool Calls (standardized)
            tool_calls = standardized_response.tool_calls
            print(f"DEBUG: In one turn we have {len(tool_calls)} tool calls", flush=True)

            # Extract token usage (provider-specific)
            input_tokens, output_tokens = self.client.extract_token_usage(response)
            
            if not tool_calls:
                # Log the model request for token tracking (no tools)
                action_logger.log_model_request(input_tokens, output_tokens, tool_calls=None, chat_history=api_history)
                # Return text only
                return "\n".join(standardized_response.text_parts)
            
            # Execute all tool calls and collect results for logging
            tool_call_results = []

            all_tools_success = True
            regular_tools = [tc for tc in tool_calls if tc.name != "complete_task"]
            complete_task_calls = [tc for tc in tool_calls if tc.name == "complete_task"]


            """AUTO NUDGING"""
            append_warning_str = ""
            # meaning that auto nudging is on and there is no complete_task call in this turn
            if auto_nudge > 0 and (len(complete_task_calls) == 0):
                # less than auto_nudge tools were used | last turn also had less than auto_nudge tools used but more than 0
                if (len(regular_tools) <= auto_nudge) and (0 < number_of_tools_used_last_turn <= auto_nudge):
                    print(f"DEBUG: Auto-nudging the model because it used less tools in parallel than it should have", flush=True)
                    append_warning_str = (
                        f"\nBATCHING REMINDER ALERT: You're making sequential calls ({number_of_tools_used_last_turn} → {len(regular_tools)}). "
                        f"STOP and THINK first, then batch ALL needed analyzing tools into ONE parallel request (5-20+ calls)."
                        f"Continue the task until it is completed. Ensure you have addressed all requirements of the current task step."
                    )
                number_of_tools_used_last_turn = len(regular_tools)
            else:
                number_of_tools_used_last_turn = 0 # we don't want complete_task_calls to influcence the nudging at all, the agent was thinking that it had finished so it is justified.


            for tool_calls_list in [regular_tools, complete_task_calls]:
                for item_index, tool_call in enumerate(tool_calls_list):
                    name = tool_call.name
                    args = tool_call.args

                    print(f"DEBUG: Executing {name}({args})", flush=True)

                    try:
                        if name in self.client.tool_map:
                            if name == "complete_task" and not all_tools_success:
                                print(f"DEBUG: complete_task was called but not all tools were successful, so we will not call it really", flush=True)
                                result = {"error": "Error: Not all tools were successful this turn so completing task is not possible"}
                                result_str = result["error"]
                            elif ((name == "complete_task" and all_tools_success) and (args.get("summary") is None or len(args.get("summary")) < 100)):
                                print(f"DEBUG: complete_task was called but the summary is too short, so we will not call it really", flush=True)
                                result = {"error": "Error: The summary is too short, it must be at least 150 characters long"}
                                result_str = result["error"]
                            else:
                                result = self.client.tool_map[name](**args)
                                if not isinstance(result, dict):
                                    result = {"result": result}
                                result_str = str(result.get("result", result))
                                if name == "run_all_tests_tool":
                                    if result.get("success"):
                                        result_run_tests_tool = f"Success: All {result.get('total_tests')} tests passed! You should now call complete_task."
                                        print("Run all tests tool was successful, so we will stop the loop FORCEFULLY", flush=True)
                                        print("We need to run the complete_task tool now manually", flush=True)
                                        self.client.tool_map["complete_task"](summary="All tests passed")
                                        # Log this manual action so it appears in the visual logger
                                        action_logger.log_action("complete_task", {"summary": "All tests passed (Auto-called)"}, "Task Completed", success=True, chat_history=api_history)
                                        stop_loop = True
                                    else:
                                        # Minimal inline filter for failures and stdout
                                        result_run_tests_tool = "--- TEST FAILURES ---\n" + "\n".join([
                                            f"Test: {f['test_name']}\nError: {f['error_msg']}\nPrints: {f['stdout']}\nTraceback: {f['traceback']}\n"
                                            for f in result.get("failures", [])
                                        ])
                                    explanation_run_tests_tool = args.get("explanation", None)
                                    print(f"DEBUG: has_run_tests_tool result: {result_run_tests_tool}, explanation: {explanation_run_tests_tool}", flush=True)

                            if result_str.startswith("Error:"): # We consider any error as a failure
                                success = False
                                all_tools_success = False
                            else:
                                success = True
                            # Log individual action for visual logger
                            action_logger.log_action(name, dict(args), result_str, success=success, chat_history=api_history)
                            # Collect result for batch token tracking
                            tool_call_results.append(StandardizedToolResult(
                                name=name,
                                args=dict(args),
                                result=result_str,
                                success=success,
                                call_id=tool_call.call_id
                            ))
                        else:
                            all_tools_success = False
                            result = {"error": f"Tool '{name}' not found."}
                            result_str = result["error"]
                            action_logger.log_action(name, dict(args), result_str, success=False, chat_history=api_history)
                            tool_call_results.append(StandardizedToolResult(
                                name=name,
                                args=dict(args),
                                result=result_str,
                                success=False,
                                call_id=tool_call.call_id
                            ))
                    except Exception as e:
                        result = {"error": str(e)}
                        all_tools_success = False
                        result_str = result["error"]
                        action_logger.log_action(name, dict(args), result_str, success=False, chat_history=api_history)
                        tool_call_results.append(StandardizedToolResult(
                            name=name,
                            args=dict(args),
                            result=result_str,
                            success=False,
                            call_id=tool_call.call_id
                        ))

                    if name == "complete_task" and all_tools_success:
                        print(f"DEBUG: model ran complete_task, so we will stop the loop FORCEFULLY", flush=True)
                        stop_loop = True
                        break  
                   
            # Log the model request with token usage and all tool calls (parallel if > 1)
            tool_call_dicts = [
            {
                "name": result.name,
                "args": result.args,
                "result": result.result,
                "success": result.success
            }
            for result in tool_call_results
            ]
            action_logger.log_model_request(input_tokens, output_tokens, tool_calls=tool_call_dicts, chat_history=api_history)

            # 6. Format and handle all tool outputs at once
            # Format all tool responses in provider-specific format
            tool_responses_formatted = self.client.format_tool_responses(tool_call_results)
            # Add them to current turn log
            # In generic_implementation.py, around line 342-350
            if result_run_tests_tool is not None:
                print("---- RESTORING HISTORY TO DEFAULT STATE (START) + RUN_TESTS_TOOL RESPONSE ----")
                print("We have run the tests tool, so we restore the history to the default state (start) + run_tests_tool response")
                current_turn_log = []  # Reset to empty
                
                # Add the test result as a model response
                self.clean_chat_history()
                for item in current_turn_log_tests:
                    current_turn_log.append(item)
                response_content = self.client.convert_to_client_schema(role="assistant", content=explanation_run_tests_tool if explanation_run_tests_tool else "No explanation provided.")
                current_turn_log_tests.append(response_content)
                current_turn_log.append(response_content)
                # Already filtered in the tool call to be only failures.
                response_content = self.client.convert_to_client_schema(role="user", content=f"The result of the tests is: {result_run_tests_tool}")
                current_turn_log.append(response_content)
                current_turn_log_tests.append(response_content)

                print(f"DEBUG: current_turn_log: {current_turn_log}", flush=True)
            else:  
                self.client.add_tool_outputs_to_turn_log(tool_responses_formatted, current_turn_log)
                if append_warning_str:
                    current_turn_log.append(self.client.convert_to_client_schema(role="user", content=append_warning_str))
            
            # CRITICAL: We DO NOT append tool_output_content to history_to_update
            # The user specifically requested to avoid saving tool responses/outputs to history.
            # We only saved the assistant's text message (without tool call details).
            
            # Loop continues... model sees (history + current_turn_log) next iteration
        
        return ""
