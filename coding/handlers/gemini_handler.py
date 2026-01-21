import os
import time
import json
from typing import Any, List, Optional
from google import genai
from google.genai import types
from coding.tools._schemas import get_tool_declarations_gemini
from coding.non_callable_tools.action_logger import action_logger
from coding.standardized_types import StandardizedResponse, StandardizedToolCall, StandardizedToolResult

class GeminiHandler:
    def __init__(self, thinking_model, model_name: str = "models/gemini-3-flash-preview", api_key: str = None):
        if api_key is None:
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
        self.base_config = types.GenerateContentConfig(safety_settings=self.safety_settings)

    def get_config(self):
        return self.base_config

    def temporary_no_tools_config(self):
        return self.base_config.model_copy(update={"tools": []})

    def convert_from_client_schema_to_text(self, content: types.Content):
        text_parts = []
        role = content.role

        # Check if content has parts
        if not hasattr(content, 'parts') or not content.parts:
            return role, ""

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
        
        thinking_budget_val = {
            "AUTO": -1,
            "NONE": 0,
            "LOW": 4096,
            "MEDIUM": 12288,
            "HIGH": 20480
        }

        if self.thinking_model:
            # For Gemini 2.5/3, include_thoughts is often required to see the process
            if self.model_name.startswith("models/gemini-3"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=True, 
                    thinking_level=thinking_level.lower()
                )
            else:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=True,
                    thinkingBudget=thinking_budget_val[thinking_level]
                )
        if tools:
            self.available_tools = tools
            self.tool_map = {tool.__name__: tool for tool in tools}
            # Use explicit schemas where available for better parameter enforcement
            config_kwargs["tools"] = get_tool_declarations_gemini(tools)

        self.base_config = types.GenerateContentConfig(**config_kwargs)

    def filter_chat_history(self, most_recent_chat: list):
        filtered_chat = []
        for content in most_recent_chat:
            # Check if content has parts
            if not hasattr(content, 'parts') or not content.parts:
                filtered_chat.append(content)
                continue

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

    def format_tool_responses(self, tool_results: List[StandardizedToolResult]):
        """Format tool results for Gemini API"""
        return [
            types.Part.from_function_response(
                name=result.name,
                response={"result": result.result} if result.success else {"error": result.result}
            )
            for result in tool_results
        ]
    
    def extract_token_usage(self, response: Any) -> tuple[int, int]:
        """Extract token usage from Gemini response"""
        if not response:
            return 0, 0

        usage_meta = getattr(response, 'usage_metadata', None)
        input_tokens = getattr(usage_meta, 'prompt_token_count', 0) if usage_meta else 0
        output_tokens = getattr(usage_meta, 'candidates_token_count', 0) if usage_meta else 0

        # Ensure we always return integers, never None
        input_tokens = input_tokens if input_tokens is not None else 0
        output_tokens = output_tokens if output_tokens is not None else 0

        return input_tokens, output_tokens

    def parse_response(self, response: Any) -> StandardizedResponse:
        """Parse Gemini response into standardized format"""
        if not response.candidates:
            return StandardizedResponse([], [], [])

        candidate = response.candidates[0]
        model_content = candidate.content

        # Check if content exists and has parts
        if not model_content or not hasattr(model_content, 'parts') or not model_content.parts:
            return StandardizedResponse([], [], [])

        text_parts = []
        thoughts = []
        tool_calls = []

        for part in model_content.parts:
            if getattr(part, 'thought', False):
                thoughts.append(part.text)
            elif part.text and not getattr(part, 'thought', False):
                text_parts.append(part.text)
            elif part.function_call:
                fc = part.function_call
                tool_calls.append(StandardizedToolCall(
                    name=fc.name,
                    args=dict(fc.args),
                    call_id=None  # Gemini doesn't use call_ids
                ))

        return StandardizedResponse(text_parts, thoughts, tool_calls)

    def add_tool_outputs_to_turn_log(self, tool_responses_formatted, current_turn_log):
        if tool_responses_formatted:
            tool_output_content = self.convert_to_client_schema(role="tool", content=tool_responses_formatted)
            current_turn_log.append(tool_output_content)

    def make_api_call(self, api_history: list, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        max_retries = 4

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=api_history,
                    config=config
                )
                return response
            except Exception as e:
                if "429" in str(e):
                    print(f"Rate limit exceeded, retrying in 10s...")
                    delay = 10
                if "500" in str(e) or "INTERNAL" in str(e) or "503" in str(e) or "504" in str(e):  # Server error
                    if attempt < max_retries - 1:
                        delay = (2 ** (attempt + 1))  # Exponential backoff: 2s, 4s, 8s
                        print(f"Server error (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                    else:
                        print(f"Failed after {max_retries} attempts: {e}")
                        print(f"The request was: {api_history}")
                        print(f"The config was: {config}")
                        raise e
                    
                    time.sleep(delay)
                    continue
                else:
                    # Non-server error, re-raise immediately
                    raise e

    def add_response_to_history(self, response: Any, current_turn_log: List, history_to_update: Optional[List] = None):
        """Add Gemini response to history"""
        if not response.candidates:
            return

        candidate = response.candidates[0]
        model_content = candidate.content

        # Check if content exists and has parts
        if not model_content or not hasattr(model_content, 'parts') or not model_content.parts:
            return

        has_tool_call = any(p.function_call for p in model_content.parts)

        if has_tool_call:
            # Preserve exact SDK object
            current_turn_log.append(model_content)

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