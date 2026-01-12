## 🔧 MODIFY_FILE_INLINE - Critical Usage Guide

**MANDATORY: Use EXACTLY these parameter names:**
- `file_path` (NOT `path`, `filepath`, `file`, `filename`)
- `diff_text` (NOT `diff`, `patch`, `content`, `patch_text`, `unified_diff`)

### Workflow (NEVER SKIP STEP 1)
1. **ALWAYS `read_file()` first** - Get current content and line numbers
2. Locate your target location using the line numbers shown
3. **Copy the actual text** from the file (3-5 lines before/after your changes)
4. Build diff using the copied text and accurate line numbers
5. `modify_file_inline(file_path="...", diff_text="...")`

### Unified Diff Format Rules

**For modifying existing files:**
```diff
@@ -LINE_NUM,CONTEXT_LEN +LINE_NUM,NEW_LEN @@
  context line 1  # Must match file content
  context line 2  # Must match file content
- line to remove  # Must match file content
+ line to add
+ another line to add
  context line 3  # Must match file content
  context line 4  # Must match file content
```

**For creating new files (after `create_file()`):**
```diff
@@ -0,0 +1,N @@
+ your content line 1
+ your content line 2
+ ...
```

**For replacing entire file:**
```diff
@@ -1,OLD_TOTAL_LINES +1,NEW_TOTAL_LINES @@
- entire old content line 1
- entire old content line 2
- ...
+ new content line 1
+ new content line 2
+ ...
```

### Common Mistakes → Fixes

**❌ Guessing line numbers:**
```diff
@@ -100,1 +100,3 @@  # WRONG - Made up numbers
 def method(self):
     pass
```

**✅ Reading file first:**
```diff
@@ -107,4 +107,8 @@  # RIGHT - Actual line numbers from read_file
     def method(self):
         """Docstring here.
         """
         pass
```

**❌ Wrong indentation:**
```diff
@@ -64,6 +64,8 @@
             self.running = False
         elif event.type == pygame.KEYDOWN:
-            self.held_keycodes.add(event.key)
+                if event.key == pygame.K_LSHIFT:  # WRONG - Bad indent
+                    self.do_dash()
```

**✅ Exact match:**
```diff
@@ -64,6 +64,8 @@
             self.running = False
         elif event.type == pygame.KEYDOWN:
             self.held_keycodes.add(event.key)  # RIGHT - Exact match
+            if event.key == pygame.K_LSHIFT:    # RIGHT - Proper indent
+                self.do_dash()
```

### Error Recovery

**"Context mismatch at line X"**
- `read_file()` again - file may have changed
- Check indentation, spacing, exact text matching
- Ensure 3-5 context lines before/after

**"Invalid diff op prefix"**
- Lines must start with ` ` (space), `+`, or `-` only
- No mixed prefixes on same line

**"No valid diff hunks found"**
- Must start with `@@ -x,y +a,b @@`
- Check for missing hunk headers
