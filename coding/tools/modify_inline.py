import os
import ast
import re
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import List, Optional, Tuple
from coding.non_callable_tools.helpers import open_file
from coding.tools.file_handling import create_file
from coding.tools.security import is_file_allowed
from coding.non_callable_tools.action_logger import action_logger


def modify_file_inline(file_path: str = None, diff_text: str = None, **kwargs) -> str:
    """
    Applies a unified diff patch to a specific file to modify its content safely.

    This function is designed to be fault-tolerant. It performs fuzzy matching on context lines
    (ignoring whitespace differences) to ensure patches apply even if indentation is slightly off.
    It creates a backup (.bak) before modifying and validates Python syntax before saving.

    IMPORTANT: This function requires EXACTLY these two parameter names:
        - file_path (not 'path', 'filepath', 'file', or 'filename')
        - diff_text (not 'patch', 'diff', 'content', 'patch_text', or 'uidiff')

    Args:
        file_path (str): The absolute or relative path to the file you want to modify.
        diff_text (str): The content of the patch in standard Unified Diff format.
            Rules for diff_text:
            1. Must contain hunk headers in the format: @@ -old_start,old_len +new_start,new_len @@
            2. Lines starting with ' ' (space) are context lines (must match existing file content).
            3. Lines starting with '-' are lines to be removed.
            4. Lines starting with '+' are lines to be added.
            5. Do NOT include file headers like '--- a/file.py' or '+++ b/file.py' if possible,
               though the tool will try to ignore them.
            6. Ensure the context lines (' ') exactly match the file content (ignoring leading/trailing whitespace).

    Returns:
        str: A text message describing the result.
            - On Success: "Successfully modified {file_path}\n\nModified lines (with ±1 context):\n{line_num}| {line_content}\n..."
            - On Failure: "Error: {error details}"
            - On No Change: "Warning: The diff was valid but resulted in identical content."

            The function NEVER raises an exception; all errors are caught and returned as strings.
            On success, the return includes the modified lines with ±1 context for verification.
    """
    print(f"[TOOL LOG] modify_file_inline called with:")
    print(f"  file_path: {file_path}")
    print(f"  diff_text length: {len(diff_text) if diff_text else 0} characters")
    if kwargs:
        print(f"  UNEXPECTED kwargs: {list(kwargs.keys())}")

    # --- 0. Check for incorrect parameter names (common LLM mistakes) ---
    if kwargs:
        wrong_params = list(kwargs.keys())
        suggestions = []

        diff_aliases = {
            "patch", "diff", "patch_text", "uidiff", "unified_diff",
            "unified_diff_format", "content", "diff_content", "patch_content"
        }
        path_aliases = {
            "path", "filepath", "file", "filename", "target_file",
            "target_path", "file_name"
        }

        for param in wrong_params:
            param_lower = param.lower()
            if param_lower in diff_aliases or "diff" in param_lower or "patch" in param_lower:
                suggestions.append(f"  - '{param}' → use 'diff_text' instead")
                if diff_text is None:
                    diff_text = kwargs[param]
                    suggestions.append(f"    (Auto-recovered: using '{param}' value as diff_text)")
            elif param_lower in path_aliases or "path" in param_lower or "file" in param_lower:
                suggestions.append(f"  - '{param}' → use 'file_path' instead")
                if file_path is None:
                    file_path = kwargs[param]
                    suggestions.append(f"    (Auto-recovered: using '{param}' value as file_path)")
            else:
                suggestions.append(f"  - '{param}' is not a valid parameter")

        warning_msg = (
            f"WARNING: Received unexpected parameter(s): {wrong_params}\n"
            f"This tool requires EXACTLY two parameters:\n"
            f"  • file_path (str): The path to the file\n"
            f"  • diff_text (str): The unified diff content\n"
            f"\nParameter suggestions:\n" + "\n".join(suggestions) + "\n"
            f"\nCorrect usage example:\n"
            f"  modify_file_inline(file_path='GameFolder/x.py', diff_text='@@ -1,3 +1,4 @@...')\n"
        )
        print(f"[TOOL LOG] {warning_msg}")

        if file_path is None or diff_text is None:
            result = f"Error: {warning_msg}"
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result
        else:
            print(f"[TOOL LOG] Auto-recovered from wrong parameter names, continuing...")

    backup_path: Optional[Path] = None
    replaced: bool = False

    try:
        # --- 1. Basic Validation ---
        if not file_path or not diff_text:
            missing = []
            if not file_path:
                missing.append("file_path")
            if not diff_text:
                missing.append("diff_text")
            result = (
                f"Error: Missing required argument(s): {missing}\n"
                f"This tool requires EXACTLY two parameters:\n"
                f"  • file_path (str): The path to the file (received: {repr(file_path)})\n"
                f"  • diff_text (str): The unified diff content (received: {'present' if diff_text else 'missing'})\n"
                f"\nCorrect usage example:\n"
                f"  modify_file_inline(file_path='GameFolder/x.py', diff_text='@@ -1,3 +1,4 @@...')"
            )
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result

        allowed = is_file_allowed(file_path, operation="write")
        if allowed is not True:
            result = f"Error: {allowed}"
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result

        if not os.path.exists(file_path):
            result = f"Error: File not found at path: {file_path}"
            message =create_file(file_path)
            if message.startswith("Error"):
                print(f"[TOOL LOG] modify_file_inline output: {result}")
                return message
            else:
                print(f"[TOOL LOG] Created file {file_path} for modification.")

        # Snapshot (best-effort)
        try:
            action_logger.snapshot_file(file_path)
        except Exception as e:
            print(f"[TOOL LOG] Warning: snapshot_file failed: {e}")

        # --- 2. Safe Read ---
        try:
            original_content = open_file(file_path)
        except UnicodeDecodeError:
            result = f"Error: File '{file_path}' is binary or not valid UTF-8 text. Cannot apply text diffs."
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result
        except Exception as e:
            result = f"Error reading file: {str(e)}"
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result

        # --- 3. Sanitize Input ---
        clean_diff = diff_text.replace("\xa0", " ")

        # --- 3.5. Special handling for empty/nearly-empty files with "create from scratch" diffs ---
        original_lines = original_content.splitlines()
        is_empty_file = (
            len(original_lines) == 0 or  # Truly empty
            (len(original_lines) == 1 and original_lines[0].strip() == "")  # Just whitespace/newline
        )
        
        skip_normal_diff = False
        if is_empty_file:
            # Work with a clean version of diff_lines for parsing
            temp_diff = clean_diff.strip()
            diff_lines = temp_diff.splitlines()
            
            # Remove markdown code fences if present
            if diff_lines and diff_lines[0].strip().startswith("```"):
                diff_lines = diff_lines[1:]
            if diff_lines and diff_lines[-1].strip().startswith("```"):
                diff_lines = diff_lines[:-1]
                
            if diff_lines and diff_lines[0].startswith("@@ -0,0 "):
                new_lines = []
                in_hunk = False
                for line in diff_lines:
                    if line.startswith("@@"):
                        in_hunk = True
                        continue
                    if not in_hunk:
                        continue
                        
                    # FIX: If the line starts with '+', it's definitely content.
                    if line.startswith("+"):
                        new_lines.append(line[1:])
                    # FIX: If the file is empty/new, lines starting with spaces 
                    # are almost certainly Python indentation, not diff context.
                    elif line.startswith(" "):
                        new_lines.append(line[1:] if len(line) > 1 else "")
                    # FIX: If it's malformed (no prefix at all), include it as-is.
                    elif not line.startswith(("-", "\\")):
                        new_lines.append(line)
        # --- 4. Apply Patch ---
        if not skip_normal_diff:
            try:
                new_content, modified_ranges = _apply_unified_diff_safe(original_content, clean_diff)
            except ValueError as ve:
                result = f"Error: Failed to apply patch: {str(ve)}"
                print(f"[TOOL LOG] modify_file_inline output: {result}")
                return result

        if new_content == original_content:
            result = "Warning: The diff was valid but resulted in identical content (no actual changes were made)."
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result

        # --- 5. Code Safety Check (Python Only) ---
        if file_path.endswith(".py"):
            is_valid, error_msg = _validate_python_code(new_content)
            if not is_valid:
                result = (
                    f"Error: syntax check failed. The patch would result in invalid Python code."
                    f"Details: {error_msg}"
                    f"Action: Review your indentation and syntax in the diff."
                )
                print(f"[TOOL LOG] modify_file_inline output: {result}")
                return result

        # --- 6. Atomic Write with backup, delete backup only on overall success ---
        backup_path = Path(file_path).with_suffix(Path(file_path).suffix + ".bak")
        try:
            shutil.copy2(file_path, backup_path)

            _atomic_replace(file_path, new_content)
            replaced = True

        except Exception as e:
            # If replace somehow partially happened (rare), restore from backup
            try:
                if backup_path.exists():
                    shutil.copy2(backup_path, file_path)
            except Exception:
                pass
            result = f"Error writing file to disk: {str(e)}"
            print(f"[TOOL LOG] modify_file_inline output: {result}")
            return result

        # Record file change (best-effort)
        try:
            action_logger.record_file_change(file_path)
        except Exception as e:
            print(f"[TOOL LOG] Warning: record_file_change failed: {e}")

        # Success: remove backup
        try:
            if backup_path and backup_path.exists():
                backup_path.unlink()
        except Exception:
            pass

        # Format the modified lines for output
        new_lines = new_content.splitlines()
        modified_snippets = []
        
        for start, end in modified_ranges:
            snippet_lines = []
            for line_num in range(start, end + 1):
                if line_num <= len(new_lines):
                    snippet_lines.append(f"{line_num:4d}| {new_lines[line_num - 1]}")
            
            if snippet_lines:
                modified_snippets.append("\n".join(snippet_lines))
        
        result = f"Successfully modified {file_path}"
        if modified_snippets:
            result += "\n\nModified lines (with ±1 context):\n"
            result += "\n...\n".join(modified_snippets)
        
        print(f"[TOOL LOG] modify_file_inline output: {result}")
        return result

    except Exception as e:
        # Best-effort restore if something went wrong after replacement
        try:
            if replaced and backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
        except Exception:
            pass

        error_trace = traceback.format_exc()
        result = f"Error: Critical System Error while applying patch: {str(e)}\nDebug Info:\n{error_trace}"
        print(f"[TOOL LOG] modify_file_inline output: {result}")
        return result
    finally:
        # If we failed after creating a backup and didn't delete it, keep it for recovery
        # but if you truly want no backups left behind, you can uncomment the cleanup below.
        # (Not recommended.)
        #
        # if backup_path and backup_path.exists() and not replaced:
        #     try:
        #         backup_path.unlink()
        #     except Exception:
        #         pass
        pass


def _atomic_replace(file_path: str, new_content: str) -> None:
    """
    Writes content to a temp file in the same directory and atomically replaces the original.
    Raises on failure.
    """
    path_obj = Path(file_path)
    temp_path = None
    fd = None
    try:
        fd, temp_path = tempfile.mkstemp(dir=str(path_obj.parent), text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_content)
        fd = None
        os.replace(temp_path, file_path)
        temp_path = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def _apply_unified_diff_safe(original_content: str, diff_text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """
    Parses and applies a unified diff.

    Changes vs your strict version:
      - Uses correct defaults for omitted hunk lengths: old_len/new_len default to 1 ONLY if the hunk
        truly represents 1 line; however in practice, diff generators omit ",len" when len==1.
        So we treat missing as 1 (that part is OK), but we DO NOT hard-fail on header length mismatches.
      - Instead, we use header lengths as a sanity-check warning only.
      - Allows empty string lines inside hunks if they are valid unified diff ops: " " (space) is an empty context line.
        A truly empty string line is treated as malformed and fails (keeps you safe).

    Returns:
        Tuple[str, List[Tuple[int, int]]]: New content and list of (start_line, end_line) tuples for modified ranges.
    
    Raises ValueError on mismatch / malformed diff.
    """
    original_lines = original_content.splitlines()

    lines = diff_text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]

    # Keep all lines; then skip file headers up to first hunk
    diff_lines = list(lines)
    first_hunk_idx = None
    for i, line in enumerate(diff_lines):
        if line.startswith("@@"):
            first_hunk_idx = i
            break
    if first_hunk_idx is not None:
        diff_lines = diff_lines[first_hunk_idx:]

    # Collect hunks
    hunks: List[List[str]] = []
    current: List[str] = []
    for line in diff_lines:
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        hunks.append(current)

    if not hunks:
        raise ValueError("No valid diff hunks found. Ensure your diff starts with '@@ -x,y +a,b @@'.")

    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    parsed_hunks = []
    for h in hunks:
        header = h[0]
        m = hunk_header_re.match(header)
        if not m:
            raise ValueError(f"Invalid hunk header: {header}")
        old_start = int(m.group(1))
        old_len = int(m.group(2)) if m.group(2) is not None else 1
        new_start = int(m.group(3))
        new_len = int(m.group(4)) if m.group(4) is not None else 1
        parsed_hunks.append(
            {
                "old_start": old_start,
                "old_len": old_len,
                "new_start": new_start,
                "new_len": new_len,
                "ops": h[1:],
                "header": header,
            }
        )

    parsed_hunks.sort(key=lambda x: x["old_start"])

    result_lines: List[str] = []
    current_src_line = 1
    modified_ranges: List[Tuple[int, int]] = []  # Track (start, end) line numbers in new file

    for hunk in parsed_hunks:
        start = hunk["old_start"]
        ops = hunk["ops"]

        located_start = _locate_hunk_start(original_lines, start, ops, window=60)
        if located_start is None:
            raise ValueError(f"Could not locate hunk starting near line {start}. File may have changed.")
        start = located_start

        while current_src_line < start:
            if current_src_line <= len(original_lines):
                result_lines.append(original_lines[current_src_line - 1])
            current_src_line += 1

        old_consumed = 0
        new_produced = 0
        hunk_start_line = len(result_lines) + 1  # Track where this hunk starts in the new file
        has_modifications = False  # Track if this hunk actually modifies anything

        for op in ops:
            if op is None:
                continue
            if op == "":
                # A truly empty string line is malformed for unified diffs (ops are prefixed).
                raise ValueError("Encountered an empty diff op line inside a hunk. Diff may be malformed.")

            cmd = op[0]
            content = op[1:]

            if cmd == " ":
                if current_src_line <= len(original_lines):
                    src_line = original_lines[current_src_line - 1]
                    if not _fuzzy_match(src_line, content):
                        context_snippet = _get_context_snippet(original_lines, current_src_line - 1)
                        raise ValueError(
                            f"Context mismatch at line {current_src_line}.\n"
                            f"Expected (from file): '{src_line.strip()}'\n"
                            f"Found (in diff):    '{content.strip()}'\n"
                            f"\nActual File Content around line {current_src_line}:\n{context_snippet}"
                        )
                    result_lines.append(src_line)
                else:
                    context_snippet = _get_context_snippet(original_lines, len(original_lines) - 1)
                    raise ValueError(
                        f"Diff expects context at line {current_src_line}, but file ended.\n"
                        f"\nActual File Content at end of file:\n{context_snippet}"
                    )
                current_src_line += 1
                old_consumed += 1
                new_produced += 1

            elif cmd == "-":
                if current_src_line <= len(original_lines):
                    src_line = original_lines[current_src_line - 1]
                    if not _fuzzy_match(src_line, content):
                        context_snippet = _get_context_snippet(original_lines, current_src_line - 1)
                        raise ValueError(
                            f"Removal mismatch at line {current_src_line}.\n"
                            f"File has: '{src_line.strip()}'\n"
                            f"Diff wants to remove: '{content.strip()}'\n"
                            f"\nActual File Content around line {current_src_line}:\n{context_snippet}"
                        )
                current_src_line += 1
                old_consumed += 1
                has_modifications = True  # Mark that this hunk has modifications

            elif cmd == "+":
                cleaned_lines = _desmash_content(content)
                for line in cleaned_lines:
                    result_lines.append(line)
                    new_produced += 1
                has_modifications = True  # Mark that this hunk has modifications

            elif cmd == "\\":
                # Marker line: does not count toward lengths
                pass

            else:
                raise ValueError(f"Invalid diff op prefix '{cmd}' in line: {op}")

        # Header length check: warn only, do not fail (reduces brittleness)
        if old_consumed != hunk["old_len"] or new_produced != hunk["new_len"]:
            print(
                "[TOOL LOG] Warning: hunk length mismatch; applying anyway.\n"
                f"  Header: {hunk['header']}\n"
                f"  Consumed old: {old_consumed} (header old_len={hunk['old_len']})\n"
                f"  Produced new: {new_produced} (header new_len={hunk['new_len']})"
            )
        
        # Record the modified range if this hunk had actual modifications
        if has_modifications:
            hunk_end_line = len(result_lines)
            # Add ±1 context lines
            context_start = max(1, hunk_start_line - 1)
            context_end = min(hunk_end_line + 1, hunk_end_line)  # Will be adjusted after all lines are added
            modified_ranges.append((context_start, context_end))

    while current_src_line <= len(original_lines):
        result_lines.append(original_lines[current_src_line - 1])
        current_src_line += 1

    # Adjust end ranges to account for final file length
    adjusted_ranges = []
    total_lines = len(result_lines)
    for start, end in modified_ranges:
        adjusted_end = min(end + 1, total_lines)
        adjusted_ranges.append((start, adjusted_end))

    return "\n".join(result_lines), adjusted_ranges


def _locate_hunk_start(original_lines: List[str], old_start: int, ops: List[str], window: int = 60) -> Optional[int]:
    """
    Relocate hunk near expected old_start using a small anchor sequence.
    Conservative approach: if no anchors exist, do not relocate.
    """
    anchors: List[str] = []
    for op in ops:
        if not op:
            continue
        if op[0] in (" ", "-"):
            anchors.append(op[1:].strip())
        if len(anchors) >= 3:
            break

    if not anchors:
        return old_start

    expected_idx = max(0, min(len(original_lines), old_start - 1))
    start_idx = max(0, expected_idx - window)
    end_idx = min(len(original_lines), expected_idx + window)

    def matches_at(i0: int) -> bool:
        j = i0
        for a in anchors:
            if j >= len(original_lines):
                return False
            if original_lines[j].strip() != a:
                return False
            j += 1
        return True

    if matches_at(expected_idx):
        return expected_idx + 1

    for delta in range(1, window + 1):
        left = expected_idx - delta
        right = expected_idx + delta
        if left >= start_idx and matches_at(left):
            return left + 1
        if right < end_idx and matches_at(right):
            return right + 1

    return None


def _is_inside_string(line: str, position: int) -> bool:
    before = line[:position]
    double_quotes = before.count('"')
    single_quotes = before.count("'")
    return (double_quotes % 2 != 0) or (single_quotes % 2 != 0)


def _desmash_content(content: str) -> List[str]:
    smashed_pattern = re.compile(r"(.+?)([\+\-])(\s{4,}.+)")
    match = smashed_pattern.search(content)
    if not match:
        return [content]

    left_part = match.group(1)
    right_part = match.group(3)

    marker_pos = len(left_part)
    if _is_inside_string(content, marker_pos):
        return [content]

    if not left_part.rstrip().endswith((")", "]", "}", '"', "'")):
        return [content]

    clean_right = right_part.lstrip()

    try:
        ast.parse(content.strip())
        return [content]
    except SyntaxError:
        pass

    try:
        ast.parse(left_part.strip())
        ast.parse(clean_right.strip())

        if left_part.strip() == clean_right.strip():
            print(f"[TOOL LOG] Detected identical smashed lines, keeping one: {left_part.strip()}")
            return [left_part]

        print(f"[TOOL LOG] Detected different smashed lines, splitting: {left_part.strip()} | {clean_right.strip()}")
        return [left_part, clean_right]
    except SyntaxError:
        return [content]


def _fuzzy_match(line_a: str, line_b: str) -> bool:
    return line_a.strip() == line_b.strip()


def _get_context_snippet(lines: List[str], center_line_idx: int, context_size: int = 5) -> str:
    start_idx = max(0, center_line_idx - context_size)
    end_idx = min(len(lines), center_line_idx + context_size + 1)

    snippet_lines = []
    for i in range(start_idx, end_idx):
        line_num = i + 1
        content = lines[i]
        marker = " <<<<<<< PROBLEM HERE" if i == center_line_idx else ""
        snippet_lines.append(f"{line_num:4d}| {content}{marker}")

    return "\n".join(snippet_lines)


def _validate_python_code(code: str) -> Tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
