from typing import Dict, Any

class StandardizedResponse:
    def __init__(self, text_parts: list, thoughts: list, tool_calls: list):
        self.text_parts = text_parts
        self.thoughts = thoughts
        self.tool_calls = tool_calls

class StandardizedToolCall:
    def __init__(self, name: str, args: dict, call_id: str, result: str = None, success: bool = True):
        self.name = name
        self.args = args
        self.call_id = call_id
        self.result = result

class StandardizedToolResult:
    def __init__(self, name: str, args: Dict[str, Any], result: str, success: bool, call_id: str = None):
        self.name = name
        self.args = args
        self.result = result
        self.success = success
        self.call_id = call_id
