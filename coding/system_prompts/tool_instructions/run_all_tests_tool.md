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
- <entity/weapon/arena>: <key numerical values discovered> (cooldowns, damage, durations, thresholds, positions)
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
- GameFolder/tests/test_orbital_cannon.py: Test expects shoot() to return list, but implementation may return None on cooldown
- GameFolder/weapons/OrbitalCannon.py: shoot() method checks last_shot_time against cooldown (2.0s), returns None if too soon
- BASE_components/BASE_weapon.py: BASE class shoot() signature returns Optional[List[Projectile]], can return None
- GameFolder/tests/test_banana_cannon.py: Similar working test resets last_shot_time=0 before calling shoot()

FILES_MODIFIED:
- GameFolder/tests/test_orbital_cannon.py: Added debug prints showing shoot() return value and last_shot_time state

FAILING_TESTS_AND_ERRORS:
- test_orbital_cannon_shooting_corners in test_orbital_cannon.py: AssertionError - assert len(projectiles) == 1 failed (got 0)
- Stack focus: OrbitalCannon.shoot() line 45-52, test line 51

ROOT_CAUSE_HYPOTHESES_CONFIRMED:
- shoot() returning None due to cooldown → Debug print showed "shoot -> None type=<class 'NoneType'>" and "last_shot_time=0.0 cooldown=2.0"

ROOT_CAUSE_HYPOTHESES_REJECTED:
- Projectile creation failing → Debug showed shoot() never reached projectile creation code, returned None earlier
- Wrong method signature → Verified BASE class signature matches implementation

DEBUG_OUTPUT_INSIGHTS:
- shoot() called with last_shot_time=0.0, but current_time in shoot() was 0.016 (from arena.update_world), so cooldown check passed
- Actually wait, need to check if test is calling shoot() before any arena updates

IMPORTANT_CONSTANTS_AND_CONFIG:
- OrbitalCannon: cooldown=2.0s, last_shot_time initialized to 0.0
- Test: Resets gun.last_shot_time = 0 before each shoot() call

LIKELY_BUG_LOCATIONS:
- test_orbital_cannon.py:test_orbital_cannon_shooting_corners: Test may be calling shoot() with wrong timing or not resetting cooldown properly

OPEN_QUESTIONS_AND_NEXT_ACTIONS:
- Need to verify: Does shoot() use arena.current_time or time.time()? → Check BASE_weapon.py for time source
- Next: If using arena.current_time, test needs to ensure arena has been updated at least once, OR shoot() should accept explicit time parameter

NEXT_ACTIONS_FOR_FIX_AGENT:
- Step 1: Read BASE_weapon.py shoot() method to confirm how it gets current time (arena.current_time vs time.time())
- Step 2: If using arena.current_time, fix test to call arena.update_world(0.016) before shoot(), OR fix implementation to use time.time() instead
- Step 3: Verify fix by checking debug output shows shoot() returns list instead of None
""")
```

**[error] WRONG - Vague explanation without structure:**
```
run_all_tests_tool(explanation="Fixed the test by adding prints and checking cooldown")
```
→ This provides NO useful information for the next agent. They will have to re-read everything.
