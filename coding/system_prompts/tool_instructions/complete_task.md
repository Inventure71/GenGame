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
- List all files modified and the nature of the changes (e.g., "Updated `GAME_weapon.py` to support dual-projectile firing")
- List any new functions, classes, or logic patterns introduced
- Identify any remaining gaps or variables that the next agent should be aware of
- **Must be at least 150 characters**
- **Output Format**: Provide a bulleted list of key technical points. Do NOT include conversational filler like "Here is what I did"

**Important Note:**
This is an INCREMENTAL summary - focus only on the most recent work since the last summary. Do not repeat what was summarized in previous task summaries. Be specific about what changed in THIS task only.

### Example Usage
**[success] CORRECT - Complete with proper summary:**
complete_task(summary="""- Modified `GameFolder/weapons/GAME_weapon.py`: Added `fire_rate` attribute and cooldown logic
- Created `GameFolder/projectiles/Missile.py`: New homing projectile class with target tracking
- Updated `GameFolder/setup.py`: Registered new weapon in `setup_battle_arena()`
- Remaining work: Need to implement collision detection for new projectile types""")

**[error] WRONG - Summary is too vague:**
complete_task(summary="I finished the task")  # WRONG - Not technical, no details