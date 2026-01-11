from google.genai import types

# =============================================================================
# EXPLICIT TOOL SCHEMAS
# =============================================================================
# These schemas override automatic schema generation for tools that the model
# frequently misuses. By providing explicit parameter names and descriptions,
# we reduce the chance of the model using wrong argument names.
# =============================================================================

TOOL_DEFINITIONS = {
    # === EXPLORATION TOOLS ===
    "get_tree_directory": {
        "name": "get_tree_directory",
        "description": (
            "Shows directory tree structure. The tree is ALREADY in your Starting Context - "
            "only call this AFTER creating new files to refresh paths. "
            "⚠️ WARNING: The directory tree is ALREADY provided in your initial context at the start of each session. "
            "Access limited to 'GameFolder' and 'BASE_components'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to explore (use 'GameFolder' or 'BASE_components')"
                }
            },
            "required": ["path"]
        }
    },
    "get_directory": {
        "name": "get_directory",
        "description": (
            "Lists immediate contents of a directory. You ONLY have access to 'GameFolder' and 'BASE_components'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (e.g., 'GameFolder/weapons')"
                }
            },
            "required": ["path"]
        }
    },
    
    # === FILE READING ===
    "read_file": {
        "name": "read_file",
        "description": (
            "Reads and returns file content with line numbers. "
            "IMPORTANT: Only use paths you discovered via get_tree_directory! Never guess paths. "
            "STRATEGY: Use full read or better get_file_outline when you don't know the file. Use line ranges when you have partial context. "
            "ALWAYS expand ranges: If you need lines 16-20, request 10-30 for better context. "
            "Reads file content with line numbers. Use paths from Starting Context or get_tree_directory. "
            "Utilize as many of these as possible in a single turn for highest efficiency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read - must be a path you discovered from get_tree_directory output"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional starting line number (1-indexed, inclusive). Use when you know approximately where to look."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional ending line number (1-indexed, inclusive). Use when you know approximately where to look."
                }
            },
            "required": ["path"]
        }
    },
    
    # === FILE MODIFICATION ===
    "modify_file_inline": {
        "name": "modify_file_inline",
        "description": (
            "Applies a unified diff patch to modify a file."
            "Include 3 lines context before/after changes. Returns modified section for verification."
            "IMPORTANT: Use EXACTLY the parameter names 'file_path' and 'diff_text'. "
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to modify (e.g., 'GameFolder/weapons/GAME_weapon.py')"
                },
                "diff_text": {
                    "type": "string",
                    "description": "The unified diff content starting with '@@ -old_start,old_len +new_start,new_len @@'."
                }
            },
            "required": ["file_path", "diff_text"]
        }
    },
    
    # === FILE CREATION ===
    "create_file": {
        "name": "create_file",
        "description": (
            "Creates an EMPTY file. Use modify_file_inline afterwards to add content."
            "Always think about what you want to insert in the file before calling this and then call both create_file and modify_file_inline in a single turn for better efficiency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path where the empty file will be created"
                }
            },
            "required": ["path"]
        }
    },

    # === TODO LIST MANAGEMENT ===
    "append_to_todo_list": {
        "name": "append_to_todo_list",
        "description": "Adds a new task to the architect's todo list. Used during the planning phase.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "A short, descriptive title for the task."
                },
                "task_description": {
                    "type": "string",
                    "description": "A detailed explanation of what needs to be done."
                }
            },
            "required": ["task_title", "task_description"]
        }
    },
    "complete_task": {
        "name": "complete_task",
        "description": "Marks the current active task as completed. MUST be called after finishing a task to move to the next one.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # === TESTING ===
    "run_all_tests_tool": {
        "name": "run_all_tests_tool",
        "description": (
            "Run all tests and return structured results with stdout logging from debug prints." 
            "CRITICAL: Use ONCE per debugging cycle." 
            "Add print() statements to all failing tests first, then run this tool to see debug output, then make fixes." 
            "Never run multiple times in one response - that's inefficient debugging."
        ),
        
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # === CODE ANALYSIS ===
    "find_function_usages": {
        "name": "find_function_usages",
        "description": (
            "Finds all locations where a specific function is used within a directory."
            "Utilize as many of these as possible in a single turn for highest efficiency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "function_name": {
                    "type": "string",
                    "description": "The name of the function to search for."
                },
                "directory_path": {
                    "type": "string",
                    "description": "The directory to search in (e.g., 'GameFolder')."
                }
            },
            "required": ["function_name", "directory_path"]
        }
    },
    "get_function_source": {
        "name": "get_function_source",
        "description": (
            "Extracts the full source code of a specific function from a file."
            "Utilize as many of these as possible in a single turn for highest efficiency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the Python file."
                },
                "function_name": {
                    "type": "string",
                    "description": "The name of the function to extract."
                }
            },
            "required": ["file_path", "function_name"]
        }
    },
    "get_file_outline": {
        "name": "get_file_outline",
        "description": (
            "Reads a file efficiently by returning only classes, methods, signatures, docstrings, AND line number ranges."
            "Use this for high-level understanding before reading specific sections."
            "Utilize as many of these as possible in a single turn for highest efficiency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the Python file."
                }
            },
            "required": ["file_path"]
        }
    },

    # === CONFLICT RESOLUTION ===
    "resolve_conflict": {
        "name": "resolve_conflict",
        "description": (
            "Resolves a specific merge conflict in a patch file. "
            "Choose 'a' for patch A's version, 'b' for patch B's, 'both' for both, or 'manual' with custom content."
            "When choosing both be aware that the indentation spaces between both need to be the same"
            "IMPORTANT: fix as many merge conflicts at once in one turn by calling this function in parallel"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patch_path": {
                    "type": "string",
                    "description": "Path to the merged patch JSON file (e.g., 'merged_patch.json')"
                },
                "file_path": {
                    "type": "string",
                    "description": "The file containing the conflict (e.g., 'GameFolder/arenas/GAME_arena.py')"
                },
                "conflict_num": {
                    "type": "integer",
                    "description": "Which conflict to resolve (1-indexed, from get_all_conflicts output)"
                },
                "resolution": {
                    "type": "string",
                    "enum": ["a", "b", "both", "manual"],
                    "description": "Resolution choice: 'a' (use patch A), 'b' (use patch B), 'both' (keep both), 'manual' (custom)"
                },
                "manual_content": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lines of code to use when resolution is 'manual'. Each array item is one line."
                }
            },
            "required": ["patch_path", "file_path", "conflict_num", "resolution"]
        }
    },
}

def get_tool_declarations_gemini(tools: list) -> list:
    """
    Convert tools into Gemini's `types.FunctionDeclaration` format.
    """
    explicit_declarations = []
    auto_callables = []
    
    for tool in tools:
        tool_name = tool.__name__
        
        if tool_name in TOOL_DEFINITIONS:
            # === HYDRATION ===
            # We take the neutral dict and convert it to Gemini's specific Object
            schema = TOOL_DEFINITIONS[tool_name]
            
            decl = types.FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=schema["parameters"]
            )
            explicit_declarations.append(decl)
            print(f"[TOOL SETUP] Using explicit schema for Gemini: {tool_name}")
        else:
            # Fallback to auto-generation using the function itself
            auto_callables.append(tool)
            print(f"[TOOL SETUP] Using auto-generated schema for: {tool_name}")
    
    result = []
    
    # 1. Wrap explicit declarations in a Tool object
    if explicit_declarations:
        result.append(types.Tool(function_declarations=explicit_declarations))
    
    # 2. Add raw callables (Gemini SDK wraps these automatically in a separate Tool object)
    if auto_callables:
        result.extend(auto_callables)
    
    return result

def get_tool_declarations_openai(tools: list) -> list:
    """
    Convert tools into OpenAI's 'Responses' API format.
    
    IMPORTANT: The 'client.responses.create' endpoint expects a FLAT structure:
    {
        "type": "function",
        "name": "...",          # <--- Top level, NOT inside "function": {...}
        "description": "...",
        "parameters": { ... }
    }
    """
    openai_tools = []

    for tool in tools:
        tool_name = tool.__name__

        if tool_name in TOOL_DEFINITIONS:
            # === HYDRATION ===
            schema = TOOL_DEFINITIONS[tool_name]
            
            # FLATTENED STRUCTURE for client.responses.create
            tool_def = {
                "type": "function",
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"]
            }
            openai_tools.append(tool_def)
            print(f"[TOOL SETUP] Using explicit schema for OpenAI: {tool_name}")
        else:
            print(f"[TOOL SETUP] WARNING: No explicit schema found for {tool_name}. "
                  "OpenAI requires explicit schemas. Skipping.")

    return openai_tools