"""
Compact Action Logger & Diff Visualizer
Tracks agent actions and provides a summary view after completion.
Includes an optional real-time visual streaming component.
"""
import os
import json
import difflib
import threading
import queue
import subprocess
import time
import socket
import atexit
import signal
from datetime import datetime
from typing import Optional, Dict, Any

class ActionLogger:
    def __init__(self, visual: bool = False):
        self.actions = []          # List of {type, name, args, result, timestamp}
        self.file_snapshots = {}   # {path: original_content} - taken before first write
        self.file_changes = {}     # {path: new_content} - after modifications
        self.start_time = None
        self.end_time = None
        
        # Token tracking
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
        self.request_count = 0
        
        # Parallel call monitoring
        self.parallel_call_stats = {
            "total_requests": 0,
            "single_tool_requests": 0,
            "parallel_tool_requests": 0,
            "sequential_read_warnings": 0
        }
        self.last_request_tool_names = []  # Track tools from previous request
        
        # Visual Logger configuration
        self.visual_enabled = visual
        # Use environment variables for host/port, default to localhost
        visual_host = os.getenv("VISUAL_LOGGER_HOST", "127.0.0.1")
        visual_port = int(os.getenv("VISUAL_LOGGER_PORT", "8765"))
        self.visual_host = visual_host
        self.visual_port = visual_port
        # For WebSocket URI, use localhost if host is 0.0.0.0 (since we're connecting from same container)
        ws_host = "127.0.0.1" if visual_host == "0.0.0.0" else visual_host
        self.visual_uri = f"ws://{ws_host}:{visual_port}/ws"
        self.visual_connected = False
        self.visual_queue = queue.Queue()
        self.visual_thread = None
        self.visual_running = False
        self.visual_server_process = None
        self.todo_list_ref = None  # Reference to the TodoList
        
        # Register cleanup
        atexit.register(self._cleanup)
    
    def save_changes_to_extension_file(self, file_path: str, name_of_backup: str = None, base_backups_root: str = "__game_backups"):
        # import only if not already imported
        if "VersionControl" not in globals():
            from coding.non_callable_tools.version_control import VersionControl

        version_control = VersionControl(self)
        return version_control.save_to_extension_file(file_path, name_of_backup=name_of_backup, base_backups_root=base_backups_root)

    def set_todo_list(self, todo_list):
        """Set reference to the TodoList for tracking."""
        self.todo_list_ref = todo_list
        if self.visual_enabled and todo_list:
            self._sync_todos()

    def _sync_todos(self):
        """Sync current TODO state to visual logger."""
        if not self.todo_list_ref:
            return
        todos = []
        for idx, task in enumerate(self.todo_list_ref.todo_list):
            todos.append({
                "id": idx,
                "title": task.task,
                "description": task.task_description,
                "completed": task.completed,
                "is_current": idx == self.todo_list_ref.index_of_current_task
            })
        self._visual_send("todo_sync", data={"todos": todos})

    def log_todo_update(self):
        """Log a TODO list update."""
        if self.visual_enabled:
            self._sync_todos()

    def _cleanup(self):
        """Cleanup resources on exit."""
        self._stop_visual_worker()
        self._stop_server()

    def _stop_server(self):
        """Stop the visual logger server if we started it."""
        if self.visual_server_process:
            try:
                print("[ActionLogger] Shutting down Visual Logger server...")
                if os.name == 'nt':
                    self.visual_server_process.terminate()
                else:
                    os.killpg(os.getpgid(self.visual_server_process.pid), signal.SIGTERM)
                self.visual_server_process.wait(timeout=2)
            except:
                pass
            self.visual_server_process = None

    def start_session(self, visual: Optional[bool] = None):
        """Start a new logging session. Optionally override the visual setting."""
        if visual is not None:
            self.visual_enabled = visual
            
        self.actions = []
        self.file_snapshots = {}
        self.file_changes = {}
        self.start_time = datetime.now()
        self.end_time = None
        
        if self.visual_enabled:
            self._ensure_server_running()
            self._start_visual_worker()
            self._visual_send("session_start")

    def _ensure_server_running(self):
        """Check if visual logger server is running, if not start it."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                # Use localhost for connection check (server might be bound to 0.0.0.0)
                check_host = "127.0.0.1"
                if s.connect_ex((check_host, self.visual_port)) == 0:
                    # Server already running
                    return
        except:
            pass
            
        print(f"[ActionLogger] Starting Visual Logger server on {self.visual_host}:{self.visual_port}...")
        server_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "visual_logger", "run_server.py")
        
        # Start server in background with host/port arguments
        self.visual_server_process = subprocess.Popen(
            [os.sys.executable, server_script, "--host", self.visual_host, "--port", str(self.visual_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        # Give it a second to start
        time.sleep(1.5)
    
    def end_session(self):
        """End the current session."""
        self.end_time = datetime.now()
        if self.visual_enabled:
            self._visual_send("session_end")
            self._stop_visual_worker()
    
    def log_action(self, tool_name: str, args: dict, result: str, success: bool = True, chat_history: list = None):
        """Log a tool call."""
        compact_args = self._compact_args(args)
        compact_result = self._compact_result(result)
        
        action = {
            "type": "tool_call",
            "name": tool_name,
            "args": compact_args,
            "args_full": args,  # Keep full args for detailed view
            "result": compact_result,
            "result_full": result,  # Keep full result for detailed view
            "success": success,
            "timestamp": datetime.now()
        }
        self.actions.append(action)
        
        if self.visual_enabled:
            self._visual_send("action", data={
                "name": tool_name,
                "args": compact_args,
                "args_full": args,
                "result": compact_result,
                "result_full": result,
                "success": success,
                "chat_history": self._serialize_chat_history(chat_history) if chat_history else None
            })
    
    def log_thinking(self, content: str, chat_history: list = None):
        """Log agent thinking/reasoning (visual only)."""
        if self.visual_enabled:
            self._visual_send("thinking", content=content, 
                              chat_history=self._serialize_chat_history(chat_history) if chat_history else None)

    def log_model_text(self, content: str, chat_history: list = None):
        """Log model text output (visual only)."""
        if self.visual_enabled:
            self._visual_send("model_text", content=content,
                              chat_history=self._serialize_chat_history(chat_history) if chat_history else None)
                              
    def log_test_result(self, test_data: dict):
        """Log a single test result."""
        if self.visual_enabled:
            self._visual_send("test_result", data=test_data)
            
    def log_test_summary(self, summary_data: dict):
        """Log test run summary."""
        if self.visual_enabled:
            self._visual_send("test_summary", data=summary_data)
    
    def log_model_request(self, input_tokens: int, output_tokens: int, tool_calls: list = None, chat_history: list = None):
        """
        Log a model API request with token usage and optional parallel tool calls.

        Args:
            input_tokens: Number of input tokens for this request
            output_tokens: Number of output tokens
            tool_calls: List of tool call dicts [{name, args, result, success}, ...] if parallel tools were called
            chat_history: The history that was sent to the model
        """
        # Ensure tokens are integers (defensive programming)
        input_tokens = int(input_tokens) if input_tokens is not None else 0
        output_tokens = int(output_tokens) if output_tokens is not None else 0

        self.request_count += 1
        cumulative_before = self.cumulative_input_tokens + self.cumulative_output_tokens

        # Update cumulative totals
        self.cumulative_input_tokens += input_tokens
        self.cumulative_output_tokens += output_tokens
        
        # Track parallel call statistics
        self.parallel_call_stats["total_requests"] += 1
        if tool_calls:
            if len(tool_calls) == 1:
                self.parallel_call_stats["single_tool_requests"] += 1
                # Check if this looks like sequential reading pattern
                current_tool_names = [tc["name"] for tc in tool_calls]
                if (self.last_request_tool_names and 
                    self.last_request_tool_names[0] == "read_file" and 
                    current_tool_names[0] == "read_file"):
                    self.parallel_call_stats["sequential_read_warnings"] += 1
                    print(f"\n[warning]  WARNING: Detected sequential read_file calls. Previous request read {len(self.last_request_tool_names)} file(s), current reads 1 file.")
                    print(f"    Consider batching file reads into a single request for better efficiency.\n")
                self.last_request_tool_names = current_tool_names
            elif len(tool_calls) > 1:
                self.parallel_call_stats["parallel_tool_requests"] += 1
                self.last_request_tool_names = [tc["name"] for tc in tool_calls]
                print(f"✓ Parallel tool usage: {len(tool_calls)} tools called in one request")
        
        request_data = {
            "request_id": self.request_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cumulative_before": cumulative_before,
            "cumulative_after": self.cumulative_input_tokens + self.cumulative_output_tokens,
            "tool_calls": tool_calls or [],
            "is_parallel": len(tool_calls) > 1 if tool_calls else False,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.visual_enabled:
            self._visual_send("model_request", data=request_data,
                              chat_history=self._serialize_chat_history(chat_history) if chat_history else None)
        
        return request_data
    
    def _serialize_chat_history(self, chat_history: list) -> list:
        """Convert chat history to a JSON-serializable format."""
        if not chat_history:
            return []
        
        serialized = []
        for content in chat_history:
            try:
                # Handle OpenAI-style dicts
                if isinstance(content, dict):
                    # Handle OpenAI function call entries specially
                    if content.get("type") == "function_call":
                        name = content.get("name", "unknown")
                        args = content.get("arguments", "{}")
                        try:
                            import json
                            parsed_args = json.loads(args) if isinstance(args, str) else args
                        except:
                            parsed_args = args

                        serialized.append({
                            "role": "assistant",
                            "parts": [{
                                "type": "function_call",
                                "name": name,
                                "args": parsed_args
                            }]
                        })
                        continue

                    # It's already a dict, just clean it up if needed
                    # Typically OpenAI history is [{"role": "user", "content": "..."}, ...]
                    # We might want to normalize it to the visual logger's expected format if it's strict,
                    # but the visual logger seems to expect "role" and "parts".
                    # Let's convert OpenAI dict to the "parts" format for consistency in the visualizer.

                    role = content.get("role", "unknown")
                    parts = []
                    
                    # Handle text content
                    txt = content.get("content")
                    if txt:
                        parts.append({"type": "text", "text": txt})
                        
                    # Handle tool calls (if stored in history - though we usually don't for OpenAI in this impl)
                    # The OpenAI handler stores tool calls in 'tool_calls' list
                    tool_calls = content.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            func = tc.get("function", {})
                            name = func.get("name")
                            args = func.get("arguments") # JSON string
                            # Try to parse args for better display
                            try:
                                import json
                                parsed_args = json.loads(args) if isinstance(args, str) else args
                            except:
                                parsed_args = args
                                
                            parts.append({
                                "type": "function_call",
                                "name": name,
                                "args": parsed_args
                            })
                            
                    serialized.append({"role": role, "parts": parts})
                    
                # Handle Gemini-style objects
                else:
                    entry = {"role": content.role, "parts": []}
                    # Check if content has parts
                    if hasattr(content, 'parts') and content.parts:
                        for part in content.parts:
                            if hasattr(part, 'text') and part.text:
                                # Skip thoughts for brevity
                                if not getattr(part, 'thought', False):
                                    entry["parts"].append({"type": "text", "text": part.text})
                            elif hasattr(part, 'function_call') and part.function_call:
                                fc = part.function_call
                                entry["parts"].append({"type": "function_call", "name": fc.name, "args": dict(fc.args) if fc.args else {}})
                    if entry["parts"]:  # Only add non-empty entries
                        serialized.append(entry)
            except Exception:
                pass  # Skip entries that can't be serialized
        return serialized

    def snapshot_file(self, path: str):
        """Take a snapshot of a file before modification."""
        if path not in self.file_snapshots:
            content = ""
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.file_snapshots[path] = content
            except FileNotFoundError:
                self.file_snapshots[path] = ""  # New file
            except Exception:
                self.file_snapshots[path] = "[BINARY OR UNREADABLE]"
                content = "[BINARY OR UNREADABLE]"
            
            if self.visual_enabled:
                self._visual_send("file_snapshot", path=path, content=content)
    
    def record_file_change(self, path: str):
        """Record the new state of a file after modification."""
        content = ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.file_changes[path] = content
        except Exception:
            self.file_changes[path] = "[BINARY OR UNREADABLE]"
            content = "[BINARY OR UNREADABLE]"
            
        if self.visual_enabled:
            self._visual_send("file_change", path=path, content=content)
    
    def _compact_args(self, args: dict) -> dict:
        """Shorten long argument values for display."""
        compact = {}
        for k, v in args.items():
            if isinstance(v, str) and len(v) > 100:
                compact[k] = v[:50] + f"...({len(v)} chars)"
            else:
                compact[k] = v
        return compact
    
    def _compact_result(self, result: str) -> str:
        """Shorten long results for display."""
        if len(result) > 200:
            return result[:100] + f"...({len(result)} chars)"
        return result
    
    def get_diff(self, path: str) -> Optional[str]:
        """Generate a unified diff for a modified file."""
        if path not in self.file_snapshots or path not in self.file_changes:
            return None
        
        old = self.file_snapshots[path].splitlines(keepends=True)
        new = self.file_changes[path].splitlines(keepends=True)
        
        diff = difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}")
        return "".join(diff)
    
    def print_summary(self, todo_list=None):
        """Print a compact summary of all actions and changes."""
        print("\n" + "="*60)
        print("  AGENT SESSION SUMMARY")
        print("="*60)
        
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            print(f"  Duration: {duration:.1f}s")
        
        # Parallel usage statistics
        stats = self.parallel_call_stats
        if stats["total_requests"] > 0:
            print(f"\n  PARALLEL TOOL USAGE:")
            print("-"*60)
            print(f"  Total requests: {stats['total_requests']}")
            print(f"  Single-tool requests: {stats['single_tool_requests']}")
            print(f"  Parallel-tool requests: {stats['parallel_tool_requests']}")
            if stats['sequential_read_warnings'] > 0:
                print(f"  [warning]  Sequential read warnings: {stats['sequential_read_warnings']}")
            parallel_pct = (stats['parallel_tool_requests'] / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
            print(f"  Parallel efficiency: {parallel_pct:.1f}%")
        
        # Tool calls summary
        print(f"\n  ACTIONS ({len(self.actions)} total):")
        print("-"*60)
        for i, action in enumerate(self.actions, 1):
            status = "✓" if action["success"] else "✗"
            name = action["name"]
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in action["args"].items())
            if len(args_str) > 50:
                args_str = args_str[:47] + "..."
            print(f"  {i:2}. [{status}] {name}({args_str})")
        
        # File changes
        changed_files = [p for p in self.file_changes if self.file_snapshots.get(p) != self.file_changes.get(p)]
        
        if changed_files:
            print(f"\n  FILES MODIFIED ({len(changed_files)}):")
            print("-"*60)
            for path in changed_files:
                diff = self.get_diff(path)
                if diff:
                    # Count additions and deletions
                    lines = diff.split('\n')
                    adds = sum(1 for l in lines if l.startswith('+') and not l.startswith('+++'))
                    dels = sum(1 for l in lines if l.startswith('-') and not l.startswith('---'))
                    print(f"  • {path}  (+{adds} -{dels})")

        # Todo list summary
        if todo_list and hasattr(todo_list, 'todo_list') and todo_list.todo_list:
            print(f"\n  TODO LIST ({len(todo_list.todo_list)} tasks):")
            print("-"*60)
            for i, task in enumerate(todo_list.todo_list, 1):
                status = "✓" if task.is_completed() else "○"
                title = task.task
                desc = task.task_description
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                print(f"  {i}. [{status}] {title}")
                print(f"      {desc}")

        print("\n" + "="*60)
    
    def print_diffs(self):
        """Print full diffs for all changed files."""
        changed_files = [p for p in self.file_changes if self.file_snapshots.get(p) != self.file_changes.get(p)]
        
        if not changed_files:
            print("No file changes detected.")
            return
        
        for path in changed_files:
            diff = self.get_diff(path)
            if diff:
                print(f"\n{'='*60}")
                print(f"DIFF: {path}")
                print('='*60)
                for line in diff.split('\n'):
                    if line.startswith('+') and not line.startswith('+++'):
                        print(f"\033[92m{line}\033[0m")  # Green
                    elif line.startswith('-') and not line.startswith('---'):
                        print(f"\033[91m{line}\033[0m")  # Red
                    elif line.startswith('@@'):
                        print(f"\033[96m{line}\033[0m")  # Cyan
                    else:
                        print(line)

    # =========================================================================
    # VISUAL LOGGER INTERNAL LOGIC
    # =========================================================================

    def _start_visual_worker(self):
        """Start the background worker thread for visual logging."""
        if self.visual_thread and self.visual_thread.is_alive():
            return
            
        self.visual_running = True
        self.visual_thread = threading.Thread(target=self._visual_worker_loop, daemon=True)
        self.visual_thread.start()

    def _stop_visual_worker(self):
        """Stop the background worker thread."""
        self.visual_running = False
        if self.visual_thread:
            self.visual_thread.join(timeout=1.0)

    def _visual_send(self, msg_type: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Queue a message to be sent to the visual logger."""
        if not self.visual_enabled:
            return
            
        message = {"type": msg_type}
        if data:
            message["data"] = data
        message.update(kwargs)
        
        self.visual_queue.put(message)

    def _visual_worker_loop(self):
        """Background thread that handles WebSocket communication."""
        try:
            from websockets.sync.client import connect
            from websockets.exceptions import ConnectionClosed
        except ImportError:
            print("[ActionLogger] 'websockets' not installed. Visual logging disabled.")
            self.visual_enabled = False
            return

        while self.visual_running:
            ws = None
            try:
                ws = connect(self.visual_uri)
                self.visual_connected = True
                
                # Set up a simple ping-pong mechanism
                last_ping_time = time.time()

                while self.visual_running:
                    try:
                        # Check for incoming messages (including pings from server)
                        try:
                            import asyncio
                            # Non-blocking receive attempt (this is a simplified approach)
                            # In a real implementation, you'd want proper async handling
                            ws.recv(timeout=0.01) 
                        except:
                            pass

                        # Send queued messages
                        msg = self.visual_queue.get(timeout=0.1)
                        ws.send(json.dumps(msg))

                        # Send pong response if we receive a ping (simplified)
                        # The websockets library should handle this automatically

                    except queue.Empty:
                        # Send periodic pong to keep connection alive (if needed)
                        current_time = time.time()
                        if current_time - last_ping_time > 25:  # Every 25 seconds
                            try:
                                # Send a keepalive message
                                ws.send(json.dumps({"type": "keepalive"}))
                                last_ping_time = current_time
                            except:
                                pass
                        continue
                    except ConnectionClosed:
                        self.visual_connected = False
                        break
                        
            except Exception:
                self.visual_connected = False
                # Try to reconnect after a short delay
                import time
                for _ in range(20):
                    if not self.visual_running: break
                    time.sleep(0.1)
            finally:
                if ws:
                    try: ws.close()
                    except: pass


# Global instance for easy access
action_logger = ActionLogger()
