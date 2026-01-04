import os
import time
from google import genai
from google.genai import types
from coding.tools._schemas import get_tool_declarations_gemini
from coding.non_callable_tools.action_logger import action_logger


class GeminiHandler:
    def __init__(self, thinking_model, model_name: str = "models/gemini-3-flash-preview"):
        api_key = os.getenv("GEMINI_API_KEY_PAID")
        self.client = genai.Client(api_key=api_key)
        self.thinking_model = thinking_model
        self.model_name = model_name
    
        self.available_tools = []
        self.tool_map = {}

        self.safety_settings = [
        types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="BLOCK_NONE"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="BLOCK_NONE"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="BLOCK_NONE"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="BLOCK_NONE"
        ),
        ]
        self.base_config_dic = None
        self.base_config = types.GenerateContentConfig(safety_settings=self.safety_settings)

    def get_config(self):
        return self.base_config

    def temporary_no_tools_config(self):
        return self.base_config.model_copy(update={"tools": []})

    def convert_from_client_schema_to_text(self, content: types.Content):
        text_parts = []
        role = content.role 
        for part in content.parts:
            if part.text:
                text_parts.append(part.text)
        return role, "\n".join(text_parts)

    def convert_to_client_schema(self, role: str, content: str | list[types.Part]):
        # Normalize role: Gemini uses "model", others use "assistant"
        if role == "assistant":
            role = "model"
        
        if isinstance(content, str):
            return types.Content(role=role, parts=[types.Part(text=content)])
        elif isinstance(content, list):
            return types.Content(role=role, parts=content)
        else:
            raise ValueError(f"Invalid content type: {type(content)}")

    def set_tools(self, tools: list):
        self.available_tools = tools
        self.tool_map = {tool.__name__: tool for tool in tools}

    def setup_config(self, thinking_level: str = "MEDIUM", system_instruction: str = None, tools: list = None):
        config_kwargs = {"system_instruction": system_instruction, "safety_settings": self.safety_settings}
        
        if self.thinking_model:
            # For Gemini 2.5/3, include_thoughts is often required to see the process
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                include_thoughts=True, 
                thinking_level=thinking_level
            )
        
        if tools:
            self.available_tools = tools
            self.tool_map = {tool.__name__: tool for tool in tools}
            # Use explicit schemas where available for better parameter enforcement
            config_kwargs["tools"] = get_tool_declarations_gemini(tools)

        self.base_config = types.GenerateContentConfig(**config_kwargs)
        self.base_config_dic = {
            "thinking_level": thinking_level,
            "system_instruction": system_instruction,
            "tools": tools
        }

    def filter_chat_history(self, most_recent_chat: list):
        filtered_chat = []
        for content in most_recent_chat:
            has_function_call = any(getattr(p, 'function_call', None) for p in content.parts)
            
            if has_function_call:
                # Convert function calls to text descriptions
                text_parts = []
                for part in content.parts:
                    if getattr(part, 'function_call', None):
                        fc = part.function_call
                        # Create a readable description of the tool call
                        args_str = ", ".join(f"{k}={v}" for k, v in fc.args.items())
                        text_parts.append(
                            types.Part(text=f"[Tool Call: {fc.name}({args_str})]")
                        )
                    elif part.text:
                        text_parts.append(part)
                
                if text_parts:
                    # Create new content with text-only parts
                    filtered_chat.append(
                        self.convert_to_client_schema(role=content.role, content=text_parts)
                    )
            else:
                # No function calls, add as-is
                filtered_chat.append(content)
        return filtered_chat

    def ask_model(self, history: list, config: types.GenerateContentConfig, history_to_update: list = None) -> str:        
        turns = 0
        max_turns = 30 # Safety cutoff
        stop_loop = False
        
        # Local list to track the conversation turn including tool outputs 
        # so the model can actually see the results of its actions during THIS turn.
        # But we will NOT append the tool outputs to self.chat_history.
        current_turn_log = [] 
        
        while turns < max_turns and not stop_loop:
            turns += 1
            print(f"DEBUG: Turn {turns}", flush=True)

            # We use history + current_turn_log for the API call
            # This ensures the model sees the tool outputs for the current interaction loop
            api_history = history + current_turn_log

            max_retries = 3

            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=api_history,
                        config=config
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if "500" in str(e) or "INTERNAL" in str(e):  # Server error
                        if attempt < max_retries - 1:
                            delay = (2 ** (attempt + 1))  # Exponential backoff: 2s, 4s, 8s
                            print(f"Server error (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                        else:
                            print(f"Failed after {max_retries} attempts: {e}")
                            print(f"The request was: {api_history}")
                            raise e
                    else:
                        # Non-server error, re-raise immediately
                        raise e
            
            if not response.candidates:
                return "Error: No candidates."

            candidate = response.candidates[0]
            model_content = candidate.content

            if candidate.finish_reason != "STOP": 
                print(f"DEBUG: Finish Reason: {candidate.finish_reason}")
            
            # Guard against None content or parts
            if not model_content or not model_content.parts:
                print(f"DEBUG: Empty response content, retrying...")
                print(f"DEBUG 2: The request was: {api_history}")
                continue
                
            if not model_content.role:
                model_content.role = "model"

            # 1. Display thoughts and text
            for part in model_content.parts:
                if getattr(part, 'thought', False):
                    print(f"\n[THOUGHT]: {part.text}", flush=True)
                    action_logger.log_thinking(part.text, chat_history=api_history)
                if part.text and not getattr(part, 'thought', False):
                    print(f"\n[MODEL]: {part.text}", flush=True)
                    action_logger.log_model_text(part.text, chat_history=api_history)

            # 2. Handle History (The Efficiency Logic)

            has_tool_call = any(p.function_call for p in model_content.parts)

            if has_tool_call:
                # IMPORTANT: Preserve the exact SDK object with thought_signature fields intact.
                current_turn_log.append(model_content)

                #if update_history:
                # OLD, keep to check if new works.Also preserve exact object in long-term history; do NOT rebuild parts.
                if history_to_update is not None:
                    # Filter thoughts out before saving to long-term memory
                    clean_parts = [p for p in model_content.parts if not getattr(p, "thought", False)]
                    if clean_parts:
                        clean_content = self.convert_to_client_schema(role="model", content=clean_parts)
                        history_to_update.append(clean_content)

            else:
                # Pure text: OK to strip thoughts to save tokens
                clean_parts = [p for p in model_content.parts if not getattr(p, "thought", False)]
                if clean_parts:
                    clean_content = self.convert_to_client_schema(role="model", content=clean_parts)
                    current_turn_log.append(clean_content)
                    if history_to_update is not None:
                        history_to_update.append(clean_content)


            # 3. Process Tool Calls
            tool_calls = [p.function_call for p in model_content.parts if p.function_call]
            print(f"DEBUG: In one turn we have {len(tool_calls)} tool calls", flush=True)

            # Extract token usage from response
            usage_meta = getattr(response, 'usage_metadata', None)
            input_tokens = getattr(usage_meta, 'prompt_token_count', 0) if usage_meta else 0
            output_tokens = getattr(usage_meta, 'candidates_token_count', 0) if usage_meta else 0
            
            if not tool_calls:
                # Log the model request for token tracking (no tools)
                action_logger.log_model_request(input_tokens, output_tokens, tool_calls=None, chat_history=api_history)
                # Return text only
                text_parts = [p.text for p in model_content.parts if p.text and not getattr(p, 'thought', False)]
                return "".join(text_parts) if text_parts else ""
            
            # Execute all tool calls and collect results for logging
            tool_call_results = []
            tool_responses = []
            
            all_tools_success = True
            regular_tools = [tc for tc in tool_calls if tc.name != "complete_task"]
            complete_task_calls = [tc for tc in tool_calls if tc.name == "complete_task"]

            for tool_calls_list in [regular_tools, complete_task_calls]:
                for tool_call in tool_calls_list:
                    name = tool_call.name
                    args = tool_call.args
                    
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

                            if result_str.startswith("Error:"): # We consider any error as a failure
                                success = False
                                all_tools_success = False
                            else:
                                success = True
                            # Log individual action for visual logger
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
                            action_logger.log_action(name, dict(args), result["error"], success=False, chat_history=api_history)
                            tool_call_results.append({
                                "name": name,
                                "args": dict(args),
                                "result": result_str,
                                "success": False
                            })
                    except Exception as e:
                        result = {"error": str(e)}
                        all_tools_success = False
                        action_logger.log_action(name, dict(args), str(e), success=False, chat_history=api_history)
                        tool_call_results.append({
                            "name": name,
                            "args": dict(args),
                            "result": str(e),
                            "success": False
                        })
                    
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=name,
                            response=result
                        )
                    )

                    if name == "complete_task" and all_tools_success:
                        print(f"DEBUG: model ran complete_task, so we will stop the loop FORCEFULLY", flush=True)
                        stop_loop = True
                        break
            
            # Log the model request with token usage and all tool calls (parallel if > 1)
            action_logger.log_model_request(input_tokens, output_tokens, tool_calls=tool_call_results, chat_history=api_history)
            
            # 4. Handle Tool Outputs
            # We add the tool outputs to current_turn_log so the model can continue working
            tool_output_content = self.convert_to_client_schema(role="tool", content=tool_responses)
            current_turn_log.append(tool_output_content)
            
            # CRITICAL: We DO NOT append tool_output_content to self.chat_history
            # The user specifically requested to avoid saving tool responses/outputs to history.
            # We only saved the TOOL CALL (in the clean_content above).
            
            # Loop continues... model sees (history + current_turn_log) next iteration
