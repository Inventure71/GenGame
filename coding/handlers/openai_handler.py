from openai import OpenAI
import os
from coding.tools._schemas import get_tool_declarations_openai
from coding.non_callable_tools.action_logger import action_logger
import json

class OpenAIHandler:
    def __init__(self, thinking_model, model_name: str = "models/gpt-5", force_url: str = None):
        if force_url is not None:
            self.client = OpenAI(
                base_url=force_url,
                api_key="ollama"
            )
        else:
            api_key = os.getenv("OPENAI_API_KEY_PAID")
            self.client = OpenAI(api_key=api_key)
        
        self.thinking_model = thinking_model
        self.model_name = model_name
    
        self.available_tools = []
        self.tool_map = {}

        # config alternative
        self.auto_summary = None # None, "auto", "concise", "detailed"
        self.reasoning = {"effort": "low", "summary": self.auto_summary}
        self.instructions = "" # system instructions
        self.tools = [] 

        self.base_config_dic = None
    
    def _as_dict(self, item):
        return item.model_dump() if hasattr(item, "model_dump") else item

    def get_config(self):
        return {"reasoning": self.reasoning, "instructions": self.instructions, "tools": self.tools}

    def temporary_no_tools_config(self):
        return {"reasoning": self.reasoning, "instructions": self.instructions, "tools": []}

    def convert_from_client_schema_to_text(self, content: dict):
        role = content["role"]
        text = content["content"]
        return role, text

    def convert_to_client_schema(self, role: str, content: str):
        # OpenAI uses "assistant" role (not "model")
        # The generic handler should pass "assistant" for model responses
        return {"role": role, "content": content}

    def set_tools(self, tools: list):
        self.available_tools = tools
        self.tool_map = {tool.__name__: tool for tool in tools}
        self.tools = get_tool_declarations_openai(tools)

    def setup_config(self, thinking_level: str = "MEDIUM", system_instruction: str = None, tools: list = None):
        self.reasoning = {"effort": f"{thinking_level.lower()}", "summary": self.auto_summary}
        self.instructions = system_instruction or "" # system instructions
        
        if tools:
            self.available_tools = tools
            self.tool_map = {tool.__name__: tool for tool in tools}
            # Use explicit schemas where available for better parameter enforcement
            self.tools = get_tool_declarations_openai(tools)

        self.base_config_dic = {
            "thinking_level": thinking_level,
            "system_instruction": system_instruction,
            "tools": tools
        }

    def filter_chat_history(self, most_recent_chat: list):
        filtered = []
        for item in most_recent_chat:
            # Case A: simple message {"role":..., "content":...}
            if isinstance(item, dict) and "role" in item and "content" in item and "type" not in item:
                filtered.append(item)
                continue

            # Case B: function call item {"type":"function_call", ...}
            if isinstance(item, dict) and item.get("type") == "function_call":
                name = item.get("name", "unknown")
                args = item.get("arguments", "{}")
                filtered.append({"role": "assistant", "content": f"[Tool Call: {name}({args})]"})
                continue

            # Otherwise ignore (function_call_output / reasoning / etc.)
        return filtered

    def ask_model(self, history: list, config: dict, history_to_update: list = None) -> str:        
        turns = 0
        max_turns = 15 # Safety cutoff
        stop_loop = False

        reasoning = config["reasoning"]
        instructions = config["instructions"]
        tools = config["tools"]

        # Local list to track the conversation turn including tool outputs 
        # so the model can actually see the results of its actions during THIS turn.
        # But we will NOT append the tool outputs to self.chat_history.
        current_turn_log = [] 
        
        while turns < max_turns and not stop_loop:
            turns += 1
            print(f"DEBUG: Turn {turns}", flush=True)

            # We use history + current_turn_log for the API call
            # This ensures the model sees the function outputs for the current interaction loop
            api_history = history + current_turn_log

            # Build API call parameters for Responses API
            api_params = {
                "model": self.model_name,
                "input": api_history,
            }

            if self.thinking_model:
                api_params["reasoning"] = reasoning
            
            # Add instructions if provided
            if instructions:
                api_params["instructions"] = instructions
            
            # Only add tools if they exist
            if tools:
                api_params["tools"] = tools

            response = self.client.responses.create(**api_params)
            
            if not response.output:
                return "Error: No output from model."
            
            # 1. Display reasoning and text content from output
            has_function_calls = False
            text_content = []
            function_calls = []

            #output_items = [self._as_dict(x) for x in response.output] 
            output_items = []    
            for x in response.output:
                item_dict = self._as_dict(x)
                # Remove output-only fields like 'status' which are not allowed in 'input'
                item_dict.pop("status", None)
                output_items.append(item_dict)
               
            
            for item in output_items:
                t = item.get("type")
                if t == "reasoning":
                    summary = item.get("summary") or []
                    for summary_item in summary:
                        txt = summary_item.get("text")
                        if txt:
                            print(f"\n[THOUGHT]: {txt}", flush=True)
                            action_logger.log_thinking(txt, chat_history=api_history)

                elif t == "message":
                    for content_item in item.get("content", []):
                        if content_item.get("type") == "output_text":
                            txt = content_item.get("text", "")
                            if txt:
                                text_content.append(txt)
                                print(f"\n[MODEL]: {txt}", flush=True)
                                action_logger.log_model_text(txt, chat_history=api_history)

                elif t == "function_call":
                    has_function_calls = True
                    function_calls.append(item)

            # 2. Handle History (The Efficiency Logic)
            if has_function_calls:
                # Add the entire model output to current turn log (for model to see in next iteration)
                current_turn_log.extend(output_items)

                # Save to long-term history (just the text content, not function calls)
                if history_to_update is not None and text_content:
                    clean_message = self.convert_to_client_schema(
                        role="assistant", 
                        content="\n".join(text_content)
                    )
                    history_to_update.append(clean_message)
                if history_to_update is not None:
                    for fc in function_calls:
                        history_to_update.append({
                            "type": "function_call",
                            "call_id": fc.get("call_id"),
                            "name": fc.get("name"),
                            "arguments": fc.get("arguments", "{}"),
                        })

            else:
                # Pure text response
                combined_text = "\n".join(text_content)
                clean_message = self.convert_to_client_schema(
                    role="assistant",
                    content=combined_text
                )
                # Add to current turn
                current_turn_log.extend(output_items)
                # Save to long-term history
                if history_to_update is not None:
                    history_to_update.append(clean_message)

            # 3. Process Function Calls
            print(f"DEBUG: In one turn we have {len(function_calls)} function calls", flush=True)

            # Extract token usage from response
            usage = response.usage if hasattr(response, 'usage') else None
            input_tokens = usage.input_tokens if usage else 0
            output_tokens = usage.output_tokens if usage else 0
            
            if not function_calls:
                # Log the model request for token tracking (no tools)
                action_logger.log_model_request(input_tokens, output_tokens, tool_calls=None, chat_history=api_history)
                # Return text only
                return "\n".join(text_content) if text_content else ""
            
            # Execute all function calls and collect results for logging
            tool_call_results = []
            function_call_outputs = []
            
            all_tools_success = True
            regular_function_calls = [tc for tc in function_calls if tc.get("name") != "complete_task"]
            complete_task_function_calls = [tc for tc in function_calls if tc.get("name") == "complete_task"]

            for function_calls_list in [regular_function_calls, complete_task_function_calls]:
                for function_calls in function_calls_list:
                    name = function_calls.get("name")
                    raw_args = function_calls.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError:
                        args = {}
                    
                    print(f"DEBUG: Executing {name}({args})", flush=True)
                    
                    try:
                        if name in self.tool_map:
                            if name == "complete_task" and not all_tools_success:
                                print(f"DEBUG: complete_task was called but not all tools were successful, so we will not call it really", flush=True)
                                result = {"error": "Error: Not all tools were successful this turn so completing task is not possible"}
                                result_str = result["error"]
                            else:   
                                result = self.tool_map[name](**args)
                                if not isinstance(result, dict):
                                    result = {"result": result}
                                result_str = str(result.get("result", result))

                            # Log individual action for visual logger
                            if result_str.startswith("Error:"): # We consider any error as a failure
                                success = False
                                all_tools_success = False
                            else:
                                success = True
                            action_logger.log_action(name, dict(args), result_str, success=success, chat_history=api_history)
                            # Collect result for batch token tracking
                            tool_call_results.append({
                                "name": name,
                                "args": dict(args),
                                "result": result_str,
                                "success": success
                            })
                        else:
                            all_tools_success = False
                            result = {"error": f"Tool '{name}' not found."}
                            result_str = result["error"]
                            action_logger.log_action(name, dict(args), result_str, success=False, chat_history=api_history)
                            tool_call_results.append({
                                "name": name,
                                "args": dict(args),
                                "result": result_str,
                                "success": False
                            })
                    except Exception as e:
                        all_tools_success = False
                        result = {"error": str(e)}
                        result_str = result["error"]
                        action_logger.log_action(name, dict(args), result_str, success=False, chat_history=api_history)
                        tool_call_results.append({
                            "name": name,
                            "args": dict(args),
                            "result": result_str,
                            "success": False
                        })
                    
                    # Format function call output for OpenAI Responses API
                    function_call_outputs.append({
                        "type": "function_call_output",
                        "call_id": function_calls.get("call_id"),
                        "output": json.dumps(result),
                    })


                    if name == "complete_task" and all_tools_success:
                        print(f"DEBUG: model ran complete_task, so we will stop the loop FORCEFULLY", flush=True)
                        stop_loop = True
                        break
            
            # Log the model request with token usage and all function calls (parallel if > 1)
            action_logger.log_model_request(input_tokens, output_tokens, tool_calls=tool_call_results, chat_history=api_history)
            
            # 4. Handle Function Call Outputs
            # We add the function outputs to current_turn_log so the model can continue working
            current_turn_log.extend(function_call_outputs)
            
            # CRITICAL: We DO NOT append function outputs to history_to_update
            # The user specifically requested to avoid saving tool responses/outputs to history.
            # We only saved the assistant's text message (without function call details).
            
            # Loop continues... model sees (history + current_turn_log) next iteration
        
        return ""