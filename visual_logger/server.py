"""
Visual Logger Server
Real-time WebSocket server for streaming agent actions to a visual frontend.
"""
import asyncio
import json
import os
import difflib
from datetime import datetime
from typing import Optional, Dict, List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
import uvicorn

app = FastAPI(title="Visual Logger")

# Store connected WebSocket clients
connected_clients: Set[WebSocket] = set()

# Session state
session_state = {
    "active": False,
    "start_time": None,
    "actions": [],
    "model_requests": [],  # Track model requests for replay/sync
    "file_snapshots": {},  # {path: content} before changes
    "file_changes": {},    # {path: content} after changes
    "file_history": {},    # {path: [{timestamp, content, action}]} - complete history
    "todos": [],           # TODO list items
    "tests": [],           # Test results
}


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send current state to new connection
        await websocket.send_json({
            "type": "state_sync",
            "data": {
                "active": session_state["active"],
                "actions": session_state["actions"],
                "model_requests": session_state["model_requests"],
                "file_history": session_state["file_history"],
                "tests": session_state.get("tests", []),
            }
        })

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Clean up dead connections
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


def generate_diff(old_content: str, new_content: str, filename: str = "") -> dict:
    """Generate a rich diff between two file contents."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    # Unified diff for display
    unified = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}"
    ))
    
    # Count changes
    additions = sum(1 for l in unified if l.startswith('+') and not l.startswith('+++'))
    deletions = sum(1 for l in unified if l.startswith('-') and not l.startswith('---'))
    
    # Side-by-side diff data
    differ = difflib.SequenceMatcher(None, old_lines, new_lines)
    side_by_side = []
    
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == 'equal':
            for idx, line in enumerate(old_lines[i1:i2]):
                side_by_side.append({
                    "type": "equal",
                    "old_line": i1 + idx + 1,
                    "new_line": j1 + idx + 1,
                    "old_content": line.rstrip('\n'),
                    "new_content": line.rstrip('\n')
                })
        elif tag == 'replace':
            max_len = max(i2 - i1, j2 - j1)
            for idx in range(max_len):
                old_idx = i1 + idx
                new_idx = j1 + idx
                side_by_side.append({
                    "type": "change",
                    "old_line": old_idx + 1 if old_idx < i2 else None,
                    "new_line": new_idx + 1 if new_idx < j2 else None,
                    "old_content": old_lines[old_idx].rstrip('\n') if old_idx < i2 else "",
                    "new_content": new_lines[new_idx].rstrip('\n') if new_idx < j2 else ""
                })
        elif tag == 'delete':
            for idx, line in enumerate(old_lines[i1:i2]):
                side_by_side.append({
                    "type": "delete",
                    "old_line": i1 + idx + 1,
                    "new_line": None,
                    "old_content": line.rstrip('\n'),
                    "new_content": ""
                })
        elif tag == 'insert':
            for idx, line in enumerate(new_lines[j1:j2]):
                side_by_side.append({
                    "type": "insert",
                    "old_line": None,
                    "new_line": j1 + idx + 1,
                    "old_content": "",
                    "new_content": line.rstrip('\n')
                })
    
    return {
        "unified": "".join(unified),
        "side_by_side": side_by_side,
        "additions": additions,
        "deletions": deletions,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial connection confirmation
        await websocket.send_json({"type": "connection_established"})

        # Start heartbeat task
        import asyncio
        heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

        try:
            while True:
                # Set a timeout for receiving messages to detect client disconnection
                data = await asyncio.wait_for(websocket.receive_json(), timeout=35.0)  # Slightly longer than ping interval
                await handle_message(data, websocket)
        finally:
            heartbeat_task.cancel()

    except asyncio.TimeoutError:
        # Client didn't respond to ping - disconnect
        pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


async def send_heartbeat(websocket: WebSocket):
    """Send periodic ping messages to keep connection alive."""
    try:
        while True:
            await asyncio.sleep(30)  # Send ping every 30 seconds
            try:
                # Send ping - if client doesn't respond within timeout, connection will close
                await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
            except Exception:
                # Connection is dead, stop heartbeat
                break
    except asyncio.CancelledError:
        pass


async def handle_message(data: dict, websocket: WebSocket = None):
    """Handle incoming messages from the logger client."""
    msg_type = data.get("type")

    if msg_type == "pong":
        # Client responded to our ping - connection is alive
        return
    elif msg_type == "session_start":
        session_state["active"] = True
        session_state["start_time"] = datetime.now().isoformat()
        session_state["actions"] = []
        session_state["model_requests"] = []
        session_state["file_snapshots"] = {}
        session_state["file_changes"] = {}
        session_state["file_history"] = {}
        session_state["todos"] = []
        session_state["tests"] = []
        await manager.broadcast({
            "type": "session_start",
            "data": {"start_time": session_state["start_time"]}
        })
        
    elif msg_type == "session_end":
        session_state["active"] = False
        await manager.broadcast({
            "type": "session_end",
            "data": {"end_time": datetime.now().isoformat()}
        })
        
    elif msg_type == "action":
        action = data.get("data", {})
        action["timestamp"] = datetime.now().isoformat()
        action["id"] = len(session_state["actions"])
        session_state["actions"].append(action)
        await manager.broadcast({
            "type": "action",
            "data": action
        })
        
    elif msg_type == "file_snapshot":
        path = data.get("path")
        content = data.get("content", "")
        session_state["file_snapshots"][path] = content
        
        # Initialize history for this file
        if path not in session_state["file_history"]:
            session_state["file_history"][path] = []
        
        session_state["file_history"][path].append({
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "action": "snapshot",
            "action_id": len(session_state["actions"]) - 1 if session_state["actions"] else 0
        })
        
        await manager.broadcast({
            "type": "file_snapshot",
            "data": {"path": path, "has_content": bool(content)}
        })
        
    elif msg_type == "file_change":
        path = data.get("path")
        content = data.get("content", "")
        old_content = session_state["file_changes"].get(path) or session_state["file_snapshots"].get(path, "")
        
        session_state["file_changes"][path] = content
        
        # Add to history
        if path not in session_state["file_history"]:
            session_state["file_history"][path] = []
            
        action_id = len(session_state["actions"]) - 1 if session_state["actions"] else 0
        
        session_state["file_history"][path].append({
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "action": "change",
            "action_id": action_id
        })
        
        # Generate diff
        diff_data = generate_diff(old_content, content, os.path.basename(path))
        
        await manager.broadcast({
            "type": "file_change",
            "data": {
                "path": path,
                "diff": diff_data,
                "action_id": action_id
            }
        })

    elif msg_type == "thinking":
        await manager.broadcast({
            "type": "thinking",
            "data": {
                "content": data.get("content", ""),
                "timestamp": datetime.now().isoformat()
            }
        })
        
    elif msg_type == "model_text":
        await manager.broadcast({
            "type": "model_text",
            "data": {
                "content": data.get("content", ""),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    elif msg_type == "todo_sync":
        todos = data.get("data", {}).get("todos", [])
        session_state["todos"] = todos
        await manager.broadcast({
            "type": "todo_sync",
            "data": {"todos": todos}
        })
    
    elif msg_type == "model_request":
        request_data = data.get("data", {})
        request_data["timestamp"] = datetime.now().isoformat()
        # Include chat_history if present (it's at top level of message)
        if "chat_history" in data:
            request_data["chat_history"] = data["chat_history"]
        # Persist for state sync/replay
        session_state["model_requests"].append(request_data)
        await manager.broadcast({
            "type": "model_request",
            "data": request_data
        })
        
    elif msg_type == "test_result":
        # Store test result for history
        if "tests" not in session_state:
            session_state["tests"] = []
        session_state["tests"].append(data.get("data", {}))
        
        await manager.broadcast({
            "type": "test_result",
            "data": data.get("data", {})
        })
        
    elif msg_type == "test_summary":
        await manager.broadcast({
            "type": "test_summary",
            "data": data.get("data", {})
        })


@app.get("/api/state")
async def get_state():
    """Get current session state."""
    return session_state


@app.get("/api/diff/{path:path}")
async def get_file_diff(path: str):
    """Get diff for a specific file."""
    old = session_state["file_snapshots"].get(path, "")
    new = session_state["file_changes"].get(path, old)
    return generate_diff(old, new, os.path.basename(path))


@app.get("/api/file-history/{path:path}")
async def get_file_history(path: str):
    """Get complete history of a file."""
    history = session_state["file_history"].get(path, [])
    return {"path": path, "history": history}


@app.get("/api/compare-versions")
async def compare_versions(path: str, version_a: int, version_b: int):
    """Compare two versions of a file."""
    history = session_state["file_history"].get(path, [])
    if version_a >= len(history) or version_b >= len(history):
        return {"error": "Version not found"}
    
    content_a = history[version_a]["content"]
    content_b = history[version_b]["content"]
    
    return generate_diff(content_a, content_b, os.path.basename(path))


# Serve static files
static_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return HTMLResponse("<h1>Visual Logger</h1><p>Frontend not found. Place index.html in frontend/</p>")


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Start the visual logger server."""
    print(f"\n{'='*60}")
    print("  VISUAL LOGGER SERVER")
    print(f"{'='*60}")
    print(f"  Open http://{host}:{port} in your browser")
    print(f"{'='*60}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


@app.get("/export/{tab_name}")
async def export_tab(tab_name: str):
    """
    Export a specific tab's data as markdown.
    Supports: flow, diff, thinking, timeline, all
    """
    from datetime import datetime
    
    def format_time(ts):
        if isinstance(ts, str):
            return ts
        return datetime.fromisoformat(ts).strftime("%H:%M:%S") if ts else ""
    
    if tab_name == "all":
        # Export everything
        md = "# Visual Logger - Complete Session Export\n\n"
        md += f"**Exported**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "---\n\n"
        
        # Export each section
        for section in ["flow", "diff", "thinking", "timeline"]:
            response = await export_tab(section)
            if response.status_code == 200:
                md += response.body.decode('utf-8') + "\n\n"
        
        return Response(content=md, media_type="text/markdown")
    
    md = ""
    
    if tab_name == "flow":
        md = "# Process Flow\n\n"
        md += f"**Total Actions**: {len(session_state['actions'])}\n\n"
        
        if session_state['actions']:
            md += "## Action Flow\n\n"
            for idx, action in enumerate(session_state['actions']):
                status = "[error]" if action.get('success') == False else "[success]"
                md += f"{idx + 1}. {status} **{action['name']}** at {format_time(action.get('timestamp'))}\n"
            md += "\n"
    
    elif tab_name == "diff":
        md = "# File Changes\n\n"
        
        files = session_state.get('file_history', {})
        if files:
            md += "## Summary\n\n"
            md += "| File | Changes |\n"
            md += "|------|----------|\n"
            
            for path, history in files.items():
                if history:
                    md += f"| `{path}` | {len(history)} version(s) |\n"
            md += "\n"
    
    elif tab_name == "thinking":
        md = "# Thoughts & Chat\n\n"
        md += "*This export captures the conversation flow between agent thoughts and model responses.*\n\n"
    
    elif tab_name == "timeline":
        md = "# Timeline\n\n"
        
        if session_state['actions']:
            md += "## Chronological Events\n\n"
            for action in session_state['actions']:
                status = "[error]" if action.get('success') == False else "[success]"
                time = format_time(action.get('timestamp'))
                md += f"### {time} - {status} {action['name']}\n\n"
                
                if action.get('args'):
                    md += "**Arguments**:\n```json\n"
                    md += json.dumps(action['args'], indent=2)
                    md += "\n```\n\n"
    
    return Response(content=md, media_type="text/markdown")


if __name__ == "__main__":
    run_server()

