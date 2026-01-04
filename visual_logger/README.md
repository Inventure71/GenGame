# Visual Logger - Enhanced Agent Monitor

A comprehensive, real-time monitoring dashboard for AI agent operations with IDE-inspired design.

## Features

### 🎯 Core Capabilities

1. **Real-Time WebSocket Streaming**
   - Live connection to agent operations
   - Automatic reconnection on disconnect
   - Visual connection status indicator

2. **Comprehensive Action Logging**
   - Every tool call logged with full details
   - Click any action to view complete arguments and results
   - Success/failure status tracking
   - Timestamp tracking for all operations

3. **Advanced Diff Viewer**
   - Side-by-side and unified diff modes
   - File modification tracking with +/- stats
   - Version comparison between any two points
   - Syntax-aware file tree with icons
   - Real-time updates as files change

4. **Thought & Chat Visualization**
   - Agent internal reasoning displayed
   - Model text responses shown separately
   - Color-coded bubbles (teal for thoughts, blue for responses)
   - Chronological chat-like interface

5. **TODO List Tracking**
   - Real-time task list synchronization
   - Visual progress indicator (completed/total)
   - Current task highlighting
   - Task descriptions for context

6. **Process Flow Graph**
   - Visual SVG-based flow diagram
   - Shows agent's journey through tasks
   - Click nodes to see action details
   - Color-coded success/failure states

7. **Interactive Timeline**
   - Chronological view of all actions
   - Expandable details for each event
   - Visual connection lines between events
   - Time-stamped entries

8. **Export to Markdown**
   - Export any tab to a formatted `.md` file
   - Click the "Export" button in the header
   - Get tables, code blocks, diffs, and diagrams
   - Share session insights with your team
   - Supports: Process Flow, Diff Viewer, Thoughts & Chat, Timeline

## Architecture

```
visual_logger/
├── server.py          # FastAPI WebSocket server
├── run_server.py      # Server launcher
├── frontend/
│   ├── index.html     # Main UI structure
│   ├── app.js         # Client application logic
│   └── styles.css     # Cyber Matrix theme styling
└── README.md          # This file
```

## Integration

### In Your Code

```python
from coding.non_callable_tools.action_logger import action_logger

# Start session with visual mode enabled
action_logger.start_session(visual=True)

# Link TODO list (optional)
action_logger.set_todo_list(todo_list)

# Log your operations (happens automatically with tools)
# The logger will:
# - Auto-start the visual server if not running
# - Stream all events in real-time
# - Track file changes and diffs
# - Display agent thoughts and responses

# End session (server auto-closes)
action_logger.end_session()
```

### Server Lifecycle

The visual logger server is **automatically managed**:
- Starts automatically when you enable visual mode
- Runs in the background on `http://127.0.0.1:8765`
- Auto-terminates when your script ends
- No manual server management needed!

## UI Layout

### Header Bar
- Connection status indicator
- Session state (Active/Idle/Completed)
- Theme toggle
- Clear session button

### Left Sidebar
- **Tasks Panel**: Shows all TODO items with progress
- **Modified Files**: File tree with modification stats

### Center Panel (Tabbed)
1. **Process Flow**: Visual graph of agent operations
2. **Diff Viewer**: File comparison with split/unified modes
3. **Thoughts & Chat**: Agent reasoning and model responses
4. **Timeline**: Chronological action log

### Right Panel
- **Action Log**: All tool calls with clickable details
- Real-time streaming
- Success/error indicators

### Bottom Status Bar
- Last action performed
- Total action count
- Session elapsed time

## Modal Details

Click any action in the Action Log to open a modal with:
- Full arguments (formatted JSON)
- Complete result output
- Execution status
- Timestamp

## Keyboard Shortcuts

- `Esc`: Close modal

## Theme

The interface uses a **Cyber Matrix** theme:
- Dark background with phosphor green accents
- Monospace fonts for code
- Smooth animations and transitions
- Color-coded elements (green=success, red=error, yellow=warning, blue=info)

## Technical Details

- **Backend**: FastAPI with WebSocket support
- **Frontend**: Vanilla JavaScript (no framework dependencies)
- **Protocol**: JSON over WebSocket
- **Charts**: Custom SVG rendering
- **Diff Algorithm**: Unified and side-by-side formats

## Message Types

The logger sends the following message types:

- `session_start` - New session initiated
- `session_end` - Session completed
- `action` - Tool call executed
- `file_snapshot` - File state before modification
- `file_change` - File modified with diff
- `thinking` - Agent internal thought
- `model_text` - Model text response
- `todo_sync` - TODO list updated
- `state_sync` - Full state synchronization

## Browser Compatibility

- Chrome/Edge (recommended)
- Firefox
- Safari
- Any modern browser with WebSocket support

## Port Configuration

Default port: `8765`

To change, modify in:
- `action_logger.py`: `self.visual_uri`
- `server.py`: `uvicorn.run(port=...)`

## Troubleshooting

**Server won't start:**
- Check if port 8765 is available
- Ensure FastAPI and dependencies are installed
- Check `visual_logger/requirements.txt`

**WebSocket won't connect:**
- Verify server is running: `lsof -i :8765`
- Check browser console for errors
- Try refreshing the page

**Thoughts not displaying:**
- Ensure `action_logger.log_thinking()` is called
- Check WebSocket connection status
- Verify messages in browser DevTools Network tab

## Future Enhancements

Potential additions:
- Export session logs to JSON/HTML
- Filtering and search capabilities
- Performance metrics and graphs
- Multi-session comparison
- Dark/Light theme toggle
- Custom color schemes
- Keyboard navigation

## Credits

Built with:
- FastAPI
- WebSockets
- Modern CSS Grid/Flexbox
- SVG for visualizations
- JetBrains Mono & Outfit fonts

