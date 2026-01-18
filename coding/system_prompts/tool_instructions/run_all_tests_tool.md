## RUN_ALL_TESTS_TOOL - Critical Usage Guide

**MANDATORY: Use EXACTLY this parameter:**
- `explanation` (REQUIRED) - A string explaining what you changed and why the tests should pass now.

### When to Call
Call `run_all_tests_tool(explanation="...")` **ONLY**:
- After adding debug prints to failing tests, OR
- After making fixes based on previous debug output
- **ONCE per debugging cycle** (never multiple times in one response)

### Explanation Format
- Be concise but specific
- Describe what you changed and why tests should pass now
- **INCLUDE ALL LEARNING FROM THIS SESSION**: Summarize key insights, patterns discovered, and debugging findings from your work so far
- Example: `"Fixed AttributeError by correcting attribute name from 'velocity' to 'vertical_velocity' to match BASE_weapon.py. Debug prints revealed the weapon was returning None due to cooldown logic - fixed by checking last_shot_time before blocking shoot()."`

### What to Include in Explanation
- **Current changes**: What you just modified in this turn
- **Session learning**: Key insights, patterns, or discoveries from previous turns
- **Debug findings**: What debug output revealed (if applicable)
- **Root cause analysis**: Why the fix should work
- **Context**: Any relevant information that helps understand the fix

### Critical Rules
- **ONE test run per response maximum**
- **Always provide explanation** - Even if just adding debug prints, explain what you're investigating
- **Pass forward learning** - Include insights from your entire debugging session, not just the current turn