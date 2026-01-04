# Visual Logger Quick Start

## 🚀 Quick Start (5 seconds)

```bash
# Option 1: Run the demo test
python visual_logger/test_visual.py

# Option 2: Use in your own code
# Just add visual=True when starting a session!
```

## 📋 What You'll See

When you run with `visual=True`, a browser window automatically opens showing:

### 1. **Left Sidebar**
- **Tasks Panel** (top): Live TODO list with progress tracking
- **Files Panel** (bottom): All modified files with +/- stats

### 2. **Center Tabs**
- **Process Flow**: Visual graph of what the agent did
- **Diff Viewer**: See exactly what changed in each file (split or unified)
- **Thoughts & Chat**: Agent's internal reasoning + model responses
- **Timeline**: Chronological list of all events

### 3. **Right Panel**
- **Action Log**: Every tool call - **CLICK THEM** to see full details!

### 4. **Click Actions for Details**
When you click any action in the Action Log, you get a modal showing:
- Full arguments (formatted JSON)
- Complete result/output
- Success/failure status
- Exact timestamp

## 🎨 Visual Features

### Color Coding
- 🟢 **Green**: Success, additions
- 🔴 **Red**: Errors, deletions  
- 🟡 **Yellow**: Warnings, updates
- 🔵 **Blue**: Info, model responses
- 🟦 **Teal**: Agent thoughts

### Interactive Elements
- Click actions → See full details
- Click files → View diffs
- Switch diff modes → Split or unified
- Tab notifications → Flash when new content arrives
- **Export button** → Download current tab as markdown

## 📥 Export to Markdown

You can export any tab to a well-formatted markdown file:

1. **Navigate** to the tab you want to export (Flow, Diff, Thoughts, Timeline)
2. **Click** the green "Export" button in the header
3. **Get** a downloadable `.md` file with:
   - Formatted tables
   - Code blocks with syntax
   - Mermaid diagrams (for Flow)
   - Complete conversation history (for Thoughts)
   - Unified diffs (for Files)
   - Chronological events (for Timeline)

### Export Formats

**Process Flow Export**:
```markdown
# Process Flow
- Mermaid diagram of action flow
- Detailed action list with args/results
- Success/failure status
```

**Diff Viewer Export**:
```markdown
# File Changes
- Summary table of all files
- Individual diffs in unified format
- Addition/deletion statistics
```

**Thoughts & Chat Export**:
```markdown
# Thoughts & Chat
- Chronological conversation
- Separated thoughts vs responses
- Timestamps for each entry
```

**Timeline Export**:
```markdown
# Timeline
- Sequential event list
- Parameters and results
- Session duration stats
```

## 🔍 Understanding the Flow

The visual logger answers:
1. **What did the agent think?** → Thoughts & Chat tab
2. **What did the agent do?** → Process Flow + Action Log
3. **What changed?** → Files panel + Diff Viewer
4. **What were the tasks?** → TODO panel
5. **When did it happen?** → Timeline tab

## 💡 Pro Tips

1. **Keep the dashboard open** while your agent runs to watch in real-time
2. **Click actions** to see complete tool call details (arguments & results)
3. **Switch to Diff Viewer** after file modifications to see changes
4. **Check Process Flow** for a bird's-eye view of the entire session
5. **Use Timeline** to understand the chronological order

## 📝 Integration Example

```python
from coding.non_callable_tools.action_logger import action_logger

# That's it! Just add visual=True
action_logger.start_session(visual=True)

# Everything else happens automatically:
# - Server starts if needed
# - Browser dashboard updates in real-time
# - All thoughts, actions, and file changes are streamed
# - Server closes when your script ends

# Optional: Link a TODO list for task tracking
action_logger.set_todo_list(todo_list)

# Your agent code here...

action_logger.end_session()
```

## 🐛 Troubleshooting

**Dashboard not loading?**
- Wait 2-3 seconds for server to start
- Manually open: http://127.0.0.1:8765

**Not seeing thoughts?**
- Check Thoughts & Chat tab (not Action Log)
- Thoughts are teal bubbles, responses are blue

**File changes not showing?**
1. Click the file in the left sidebar
2. Check the Diff Viewer tab

**Server won't start?**
```bash
# Check if port is in use
lsof -i :8765

# Install dependencies if needed
pip install -r visual_logger/requirements.txt
```

## ⚡ Demo Test

Run the included test to see all features:

```bash
python visual_logger/test_visual.py
```

This will:
- Start the visual logger
- Create 3 TODO items
- Log some thoughts
- Execute tool calls  
- Modify a file
- Complete all tasks

Check each tab in the dashboard to see all the data!

## 🎯 Key Takeaway

The visual logger gives you **complete visibility** into what your AI agent is doing, thinking, and changing - all in real-time with a beautiful, interactive interface.

No more guessing! Just enable `visual=True` and watch the magic happen. 🪄

