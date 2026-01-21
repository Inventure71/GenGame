## RUN_ALL_TESTS_TOOL - Critical Usage Guide

**MANDATORY: Use EXACTLY this parameter:**
- `explanation` (REQUIRED) - A string explaining what you changed and why the tests should pass now.

### When to Call
Call `run_all_tests_tool(explanation="...")` **ONLY**:
- After adding debug prints to failing tests, OR
- After making fixes based on previous debug output
- **ONCE per debugging cycle** (never multiple times in one response)

### Explanation Format = KNOWLEDGE HANDOFF (MANDATORY)

The `explanation` is **not** just "why tests should pass".  
It is a **knowledge capsule** for the NEXT AGENT. Treat it as the ONLY memory that survives.

**You MUST follow this exact structure:**

```text
FILES_READ:
- <file_path>: <why this file is important / what you learned from it>
- ...

FILES_MODIFIED:
- <file_path>: <what you changed and why>
- ...

FAILING_TESTS_AND_ERRORS:
- <test_name> in <file>: <error type + short message>
- Stack focus: <relevant function / method names and line ranges>
- ...

ROOT_CAUSE_HYPOTHESES_CONFIRMED:
- <short statement of confirmed root cause> → <evidence that confirmed it>
- ...

ROOT_CAUSE_HYPOTHESES_REJECTED:
- <idea you tried> → <evidence that disproved it> (important to avoid re-trying)
- ...

DEBUG_OUTPUT_INSIGHTS:
- <what prints/logs showed> (actual vs expected values, state transitions, cooldown/timer behavior, etc.)
- ...

IMPORTANT_CONSTANTS_AND_CONFIG:
- <entity/ability/arena>: <key numerical values discovered> (cooldowns, damage, durations, thresholds, positions)
- ...

LIKELY_BUG_LOCATIONS:
- <file>:<function or class>: <why this is probably wrong>
- ...

OPEN_QUESTIONS_AND_AMBIGUITIES:
- <uncertain behavior> + <what would need to be checked next>
- ...

NEXT_ACTIONS_FOR_FIX_AGENT:
- Step 1: <concrete first check or change>
- Step 2: <next concrete action>
- ...
```

**Rules:**

- Always fill **every section** (write `NONE` if truly nothing, but think hard first).
- Be **specific**: mention exact files, classes, methods, attributes, constants.
- Capture **both**: what worked and what you already tried that didn't work.
- Assume the next agent **cannot see your past thoughts or tool calls**; this handoff is all they get.
- **No fluff** - Every bullet should help the next agent avoid re-doing work.

### What to Include in Explanation

- **Current changes**: What you just modified in this turn
- **Session learning**: Key insights, patterns, or discoveries from previous turns
- **Debug findings**: What debug output revealed (if applicable)
- **Root cause analysis**: Why the fix should work
- **Context**: Any relevant information that helps understand the fix
- **Rejected hypotheses**: What you tried that didn't work (to avoid re-trying)

### Critical Rules

- **ONE test run per response maximum**
- **Always provide explanation** - Even if just adding debug prints, explain what you're investigating
- **Pass forward learning** - Include insights from your entire debugging session, not just the current turn
- **Use the template** - Follow the structured format above to ensure nothing is forgotten

### Example Usage

**[success] CORRECT - Complete handoff with structured format:**
```
run_all_tests_tool(explanation="""
FILES_READ:
- GameFolder/tests/mandatory_edge_cases_test.py: Tests effect damage cooldown timing
- GameFolder/effects/waveprojectileeffect.py: Effect update and lifetime logic
- GameFolder/arenas/GAME_arena.py: Effect damage cooldown enforcement

FILES_MODIFIED:
- GameFolder/tests/mandatory_edge_cases_test.py: Added debug prints showing effect hit timestamps

FAILING_TESTS_AND_ERRORS:
- test_effect_damage_cooldown in mandatory_edge_cases_test.py: AssertionError - cooldown not enforced
- Stack focus: GameFolder/arenas/GAME_arena.py:_apply_effects and test line 22

ROOT_CAUSE_HYPOTHESES_CONFIRMED:
- effect_hit_times key mismatch → Debug showed network_id missing causing new key each frame

ROOT_CAUSE_HYPOTHESES_REJECTED:
- Effect lifetime too short → Effect still present after cooldown window

DEBUG_OUTPUT_INSIGHTS:
- effect_hit_times keys used effect.network_id but network_id was None
- current_time advanced correctly but key never matched

IMPORTANT_CONSTANTS_AND_CONFIG:
- RadialEffect: damage_cooldown=1.0s
- Arena: effect_hit_times dict keyed by (effect.network_id, cow.id)

LIKELY_BUG_LOCATIONS:
- GameFolder/arenas/GAME_arena.py:_apply_effects: missing network identity for effects

OPEN_QUESTIONS_AND_AMBIGUITIES:
- Should effects use network_id or fall back to object id when missing?

NEXT_ACTIONS_FOR_FIX_AGENT:
- Step 1: Ensure all effects set network identity on creation
- Step 2: If network_id missing, key by id(effect) instead
- Step 3: Re-run tests to confirm cooldown enforcement
""")
```

**[error] WRONG - Vague explanation without structure:**
```
run_all_tests_tool(explanation="Fixed the test by adding prints and checking cooldown")
```
→ This provides NO useful information for the next agent. They will have to re-read everything.
