# Task Summary Instruction

Summarize the work you have just completed for the current task.

## Requirements:
- Be concise and technical.
- List all files modified and the nature of the changes (e.g., "Updated `GAME_character.py` to add a new primary ability").
- List any new functions, classes, or logic patterns introduced.
- Identify any remaining gaps or variables that the next agent should be aware of.
- **Output Format**: Provide a bulleted list of key technical points. Do NOT include conversational filler like "Here is what I did".

## Important Note:
This is an INCREMENTAL summary - focus only on the most recent work since the last summary. Do not repeat what was summarized in previous task summaries. Be specific about what changed in THIS task only.

## Example Format:
- Modified `GameFolder/characters/GAME_character.py`: Added a new passive ability hook and tuning
- Created `GameFolder/effects/waveprojectileeffect.py`: New area effect with cooldown tracking
- Updated `GameFolder/arenas/GAME_arena.py`: Integrated ability pickup handling
- Remaining work: Add tests for the new effect cooldown edge case
