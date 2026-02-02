## RUN_ALL_TESTS_TOOL - Critical Usage Guide

**MANDATORY: Use EXACTLY this parameter:**
- `explanation` (REQUIRED) - A complete knowledge handoff for the next agent (see format below).

### Tone and framing of the explanation (MANDATORY)

**Never assume or claim that you fixed something.** You do not know whether the tests will pass or whether your changes were correct. The explanation is read by the next agent, who may see failing tests; they need to know what you actually did and what you learned, not a story about fixes that worked.

**Do this instead:**
- **What you changed:** Describe each change precisely (file, location, before/after). Do not say "Fixed X"; say "Added import of Y in file Z", "Changed constant A from 40 to 30 in …", "Added serialize/deserialize to class W".
- **What you learned:** State what you inferred from errors, stack traces, and code (e.g. "The test expects display name without hyphen", "effect_hit_times is keyed by network_id", "Ability dict was missing 'activate' key").
- **What you hope was addressed:** Optionally state what you intended each change to address (e.g. "Hoped this would resolve the KeyError for 'activate'"). That way, if tests still fail, the next agent knows what was already tried and what might still be wrong.

Write the explanation so that if something is still broken or your fixes did not work, the next agent has everything they need: your precise changes, your reasoning, and your hypotheses. They should not have to guess what you did or re-read files you already read.

### When to Call
Call `run_all_tests_tool(explanation="...")` **ONLY**:
- After adding debug prints to failing tests, OR
- After making fixes based on previous debug output
- **ONCE per debugging cycle** (never multiple times in one response)

### Explanation Format = KNOWLEDGE HANDOFF (MANDATORY)

**Memory is wiped after this call** — the next agent sees only your `explanation`. Pass everything you learned (changes, code snippets with line numbers, hypotheses, debug output, next steps) so they can continue without re-reading files. Do not claim you fixed things; describe what you changed, what you learned, and what you hoped to fix. See fix_agent.md §3 for the full template; use the structure below as minimum.

```text
FILES_READ:
- <file_path>: <why this file is important / what you learned from it>
- ...

FILES_MODIFIED:
- <file_path>: <precise description of each change — what was added/removed/changed, at which lines; do not say "Fixed X", describe the concrete edit and what you hoped it would address>
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

### Critical Rules

- **ONE test run per response maximum**
- **Test order** — If the first test in a file fails (import/setup/headless), later tests may not run; note this in the explanation so the next agent fixes setup first.
- **Fill every section** of the explanation template; write `NONE` only if truly empty.
- **Be specific** — files, line numbers, signatures, constants, what you tried and what you learned.

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
