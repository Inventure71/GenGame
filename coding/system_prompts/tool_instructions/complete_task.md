## COMPLETE_TASK - Critical Usage Guide

**MANDATORY: Use EXACTLY this parameter:**
- `summary` (REQUIRED) - A bulleted list summarizing the work completed for this task. **Must be at least 150 characters.**

### When to Call
Call `complete_task(summary="...")` **ONLY** when:
- Feature is fully implemented
- All tests pass (only if applicable)
- `setup.py` registration is done (if applicable)
- No pending fixes or syntax errors
- You are 100% confident the task is complete

### Summary Format Requirements
The `summary` parameter must follow the same format as task summaries (see `summarize_history.md`):

**Requirements:**
- Be concise and technical
- List all files modified and the nature of the changes (e.g., "Updated `GAME_character.py` to add a new passive ability")
- List any new functions, classes, or logic patterns introduced
- Identify any remaining gaps or variables that the next agent should be aware of
- **Must be at least 150 characters**
- **Output Format**: Provide a bulleted list of key technical points. Do NOT include conversational filler like "Here is what I did"

**Important Note:**
This is an INCREMENTAL summary - focus only on the most recent work since the last summary. Do not repeat what was summarized in previous task summaries. Be specific about what changed in THIS task only.

### Example Usage
**[success] CORRECT - Complete with proper summary:**
complete_task(summary="""- Modified `GameFolder/characters/GAME_character.py`: Added a new primary ability handler
- Created `GameFolder/effects/GAME_effects.py`: Added a timed area effect with draw/update logic
- Updated `GameFolder/arenas/GAME_arena.py`: Integrated pickup handling for abilities
- Remaining work: Add tests for the new effect cooldown edge case""")

**[error] WRONG - Summary is too vague:**
complete_task(summary="I finished the task")  # WRONG - Not technical, no details
