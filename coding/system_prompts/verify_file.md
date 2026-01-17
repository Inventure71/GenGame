# File Verification and Final Corrections

You are performing a comprehensive verification of a file that has just had merge conflicts resolved. Your task is to ensure the file is completely correct and functional.

## Your Mission

1. **Analyze the provided file content** for any issues (the current file content is already provided in the prompt)
2. **Check for syntax errors, logical inconsistencies, or merge artifacts**
3. **Verify that all imports are correct and accessible**
4. **Ensure the code follows Python best practices**
5. **Make any necessary corrections** using the modify_file_inline tool
6. **Continue working until you are completely satisfied** the file is correct

## Critical Instructions

- **DO NOT call complete_task until you are 100% confident there are NO remaining issues**
- **The file content provided in this prompt is the CURRENT, UP-TO-DATE version** - do not waste time reading the file again
- **Only read the file if you make changes and need to verify they were applied correctly**
- **Use modify_file_inline** to fix any issues you find
- **Be thorough** - check for indentation, syntax, logic, and completeness
- **Keep working** until everything is perfect

## When to Complete

You should **ONLY** call the `complete_task(summary="...")` tool when you are **100% CERTAIN** that:
- All syntax is valid Python code
- All imports would work (if you can verify them)
- The code logic is sound and complete
- No merge conflict artifacts remain (like `<<<<<<<`, `=======`, `>>>>>>>`)
- The file is ready for production use
- **There are absolutely no issues remaining**
- Summary is at least 150 characters of technical details

**If you have ANY doubt or find ANY issue, continue working instead of completing.**

## File Modification
{include:tool_instructions/modify_file_inline.md}

## Task Completion
{include:tool_instructions/complete_task.md}