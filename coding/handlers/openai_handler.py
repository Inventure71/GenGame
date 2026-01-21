from openai import OpenAI
import os
from typing import Any, List, Optional
from coding.tools._schemas import get_tool_declarations_openai
from coding.non_callable_tools.action_logger import action_logger
from coding.standardized_types import StandardizedResponse, StandardizedToolCall, StandardizedToolResult
import json

class OpenAIHandler:
    def __init__(self, thinking_model, model_name: str = "models/gpt-5", force_url: str = None, api_key: str = None):
        if force_url is not None:
            self.client = OpenAI(
                base_url=force_url,
                api_key="ollama"
            )
        else:
            if api_key is None:
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



    def format_tool_responses(self, tool_results: List[StandardizedToolResult]):
        """Format tool results for OpenAI API"""
        return [
            {
                "type": "function_call_output",
                "call_id": result.call_id,
                "output": json.dumps({"result": result.result} if result.success else {"error": result.result})
            }
            for result in tool_results
        ]
    
    def extract_token_usage(self, response: Any) -> tuple[int, int]:
        """Extract token usage from OpenAI response"""
        if not response:
            return 0, 0

        usage = response.usage if hasattr(response, 'usage') else None
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0

        # Ensure we always return integers, never None
        input_tokens = input_tokens if input_tokens is not None else 0
        output_tokens = output_tokens if output_tokens is not None else 0

        return input_tokens, output_tokens
    
    def parse_response(self, response: Any) -> StandardizedResponse:
        """Parse OpenAI response into standardized format"""
        if not response.output:
            return StandardizedResponse([], [], [])
        
        text_parts = []
        thoughts = []
        tool_calls = []
        
        for item in response.output:
            item_dict = self._as_dict(item)
            
            if item_dict.get("type") == "reasoning":
                summary = item_dict.get("summary") or []
                for summary_item in summary:
                    txt = summary_item.get("text")
                    if txt:
                        thoughts.append(txt)
            
            elif item_dict.get("type") == "message":
                for content_item in item_dict.get("content", []):
                    if content_item.get("type") == "output_text":
                        txt = content_item.get("text", "")
                        if txt:
                            text_parts.append(txt)
            
            elif item_dict.get("type") == "function_call":
                tool_calls.append(StandardizedToolCall(
                    name=item_dict.get("name"),
                    args=json.loads(item_dict.get("arguments", "{}")),
                    call_id=item_dict.get("call_id")
                ))
        
        return StandardizedResponse(text_parts, thoughts, tool_calls)
    
    def make_api_call(self, api_history: list, config: dict):
        """Make OpenAI API call"""
        api_params = {
            "model": self.model_name,
            "input": api_history,
        }
        
        reasoning = config["reasoning"]
        instructions = config["instructions"]
        tools = config["tools"]
        
        if self.thinking_model:
            api_params["reasoning"] = reasoning
        
        if instructions:
            api_params["instructions"] = instructions
            
        if tools:
            api_params["tools"] = tools
        
        return self.client.responses.create(**api_params)
    
    def add_response_to_history(self, response: Any, current_turn_log: List, history_to_update: Optional[List] = None):
        """Add OpenAI response to history"""
        output_items = []
        text_content = []
        function_calls = []
        has_function_calls = False
        
        for x in response.output:
            item_dict = self._as_dict(x)
            item_dict.pop("status", None)
            output_items.append(item_dict)
            
            if item_dict.get("type") == "message":
                for content_item in item_dict.get("content", []):
                    if content_item.get("type") == "output_text":
                        txt = content_item.get("text", "")
                        if txt:
                            text_content.append(txt)
            
            elif item_dict.get("type") == "function_call":
                has_function_calls = True
                function_calls.append(item_dict)
        
        if has_function_calls:
            current_turn_log.extend(output_items)
            
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
            combined_text = "\n".join(text_content)
            clean_message = self.convert_to_client_schema(
                role="assistant",
                content=combined_text
            )
            current_turn_log.extend(output_items)
            if history_to_update is not None:
                history_to_update.append(clean_message)
    
    def add_tool_outputs_to_turn_log(self, tool_responses_formatted, current_turn_log):
        """Add formatted tool responses to current turn log"""
        if tool_responses_formatted:
            current_turn_log.extend(tool_responses_formatted)