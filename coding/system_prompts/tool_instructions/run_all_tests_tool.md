## RUN_ALL_TESTS_TOOL - Critical Usage Guide

**MANDATORY: Use EXACTLY this parameter:**
- `explanation` (REQUIRED) - A string explaining what you changed and why the tests should pass now.

### When to Call
Call `run_all_tests_tool(explanation="...")` **ONLY**:
- After adding debug prints to failing tests, OR
- After making fixes based on previous debug output
- **ONCE per debugging cycle** (never multiple times in one response)

### Explanation Format = KNOWLEDGE HANDOFF (MANDATORY)

**🚨 CRITICAL: Memory Loss After `run_all_tests_tool()` 🚨**

When you call `run_all_tests_tool()`, your memory is **IMMEDIATELY WIPED**.  
The next agent receives **ONLY** your `explanation` parameter.  
If tests fail, the next agent has **ZERO** knowledge of what you learned.  
**YOU MUST PASS EVERYTHING YOU LEARNED** in the `explanation`.

The `explanation` is **not** just "why tests should pass".  
It is a **complete knowledge dump** for the NEXT AGENT. Treat it as the ONLY memory that survives.

**Detail requirement:** Include enough information (code snippets with line numbers, function signatures, constants, debug output, execution traces) that the next agent **DOES NOT NEED TO RE-READ ANY FILES** you already read. They should be able to continue debugging directly from your explanation.

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

- **Include code snippets with line numbers** - Don't just reference files, include the actual code the next agent needs to see
- **Include function signatures** - Document exact parameter names, types, return values
- **Include attribute/constant values** - Document exact numeric values, default values, where they're defined
- **Include debug output** - Show actual vs expected values, state transitions, timestamps
- **Include execution traces** - Document step-by-step execution order you analyzed
- Always fill **every section** (write `NONE` if truly nothing, but think hard first).
- Be **specific**: mention exact files, classes, methods, attributes, constants, line numbers.
- Capture **both**: what worked and what you already tried that didn't work.
- Assume the next agent **cannot see your past thoughts or tool calls**; this handoff is all they get.
- **Detail level:** The next agent should NOT need to re-read any files you already read. They should be able to continue debugging directly from your explanation.
- **No fluff** - Every bullet should help the next agent avoid re-doing work.

### What to Include in Explanation (COMPLETE KNOWLEDGE DUMP)

**You must include EVERYTHING you learned, not just current changes:**

- **All files read**: Every file you read, with relevant code snippets (with line numbers), function signatures, key logic
- **All functions/methods inspected**: Exact signatures, parameter names, return types, line ranges, key logic
- **All attributes/constants discovered**: Exact values, where they're defined, default values
- **All code changes made**: File paths, line ranges, old code → new code, why each change was made
- **All hypotheses tested**: Which confirmed (with evidence), which rejected (with evidence)
- **All debug output**: Actual vs expected values, state transitions, timestamps, cooldown behavior
- **All execution order traces**: Step-by-step analysis of method execution, where order problems were found
- **All constants/config**: Cooldowns, damage values, durations, thresholds, coordinates (with exact values and locations)
- **All bug locations**: File:function:line, why it's suspect, relevant code snippets
- **All next steps**: Exact file paths, function names, specific checks the next agent should perform

**Detail requirement:** The next agent should be able to continue debugging **WITHOUT re-reading any files you already read**. Include enough code snippets, line numbers, and context that they can work directly from your explanation.

### Critical Rules

- **ONE test run per response maximum**
- **Memory loss after call** - Your memory is wiped immediately after `run_all_tests_tool()` returns. The next agent only sees your `explanation`.
- **Always provide explanation** - Even if just adding debug prints, explain what you're investigating
- **Pass forward ALL learning** - Include insights from your entire debugging session, not just the current turn
- **Include code snippets** - Don't just reference files, include actual code with line numbers
- **Include function signatures** - Document exact parameter names, types, return values
- **Include constants/values** - Document exact numeric values, where they're defined
- **Include debug output** - Show actual vs expected values, state transitions
- **Include execution traces** - Document step-by-step execution order analysis
- **Use the template** - Follow the structured format above to ensure nothing is forgotten
- **Detail level** - The next agent should NOT need to re-read any files you already read

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
