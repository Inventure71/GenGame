# AGENTS.md - GenGame Development Guidelines

This file contains essential information for agentic coding assistants working on the GenGame project. It includes build/lint/test commands, code style guidelines, and project conventions.

## Build/Lint/Test Commands

### Testing
```bash
# Run all tests (base game tests + custom GameFolder tests)
python testing.py

# Run specific test file (modify BASE_tests.py to target specific tests)
# Note: Individual test targeting requires manual modification of BASE_components/BASE_tests.py

# Run tests programmatically
from coding.tools.testing import run_all_tests_tool
results = run_all_tests_tool()
print(results)
```

### Building & Running
```bash
# Install dependencies
pip install -r requirements.txt

# Run the game menu
python main.py

# Run the game server
python server.py --host 127.0.0.1 --port 5555

# Run with Docker
docker build -t gengame .
docker run -p 5555:5555 gengame
```

### Visual Logger (Development Tool)
```bash
# Run visual logger demo (opens browser dashboard)
python visual_logger/test_visual.py

# Use visual logger in agent code
from coding.non_callable_tools.action_logger import action_logger
action_logger.start_session(visual=True)
# ... your code ...
action_logger.end_session()
```

### Development Scripts
```bash
# Manual REPL for testing agent tools
python testing.py  # Uncomment main_manual_repl() call

# Version control operations
python testing.py  # Uncomment main_version_control() call

# Interactive conflict resolution
python testing.py  # Uncomment main_version_control_interactive() call
```

## Code Style Guidelines

### Naming Conventions
- **Classes**: PascalCase (`BaseCharacter`, `BaseMenu`, `NetworkClient`)
- **Methods/Functions**: snake_case (`take_damage`, `run_menu_loop`, `move`)
- **Variables**: snake_case (`vertical_velocity`, `spawn_location`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_LIVES`, `GRAVITY`)
- **Private Methods**: Leading underscore (`_apply_patch_async`)
- **Files**: snake_case with descriptive names (`base_character.py`, `network_client.py`)

### File Organization
- **BASE_** prefix: Core engine components in `BASE_components/` and `BASE_files/` (read-only)
- **GameFolder/**: Custom game implementations that inherit from BASE_ classes
- **coding/**: Agent/AI related code and tools
- **__patches/**: Game modification patches
- **__game_backups/**: Automatic backups during development

### Import Organization
```python
# Standard library imports
import os
import sys
import time

# Third-party imports
import pygame
import fastapi
from dotenv import load_dotenv

# Local imports - grouped by package
from BASE_components.BASE_character import BaseCharacter
from BASE_files.BASE_menu import BaseMenu
from coding.tools.testing import run_all_tests_tool
```

### Type Hints
Use type hints consistently:
```python
def __init__(self, name: str, location: list[float, float], width: float = 30.0):
    self.health: float = 100.0
    self.weapon: Optional[BaseWeapon] = None
    self.location: list[float, float] = location
```

### Code Structure Patterns

#### Class Structure
```python
class GameCharacter(BaseCharacter):
    def __init__(self, name: str, location: list[float, float]):
        super().__init__(name, "Custom character", "character.png", location)
        # Custom initialization
        self.custom_attribute = 0

    def update(self, delta_time: float, platforms: list, arena_height: int):
        # Custom update logic
        super().update(delta_time, platforms, arena_height)
        # Additional behavior
```

#### Method Documentation
Methods should be self-documenting through clear naming and structure. Avoid redundant comments.

#### Error Handling
```python
try:
    result = risky_operation()
except SpecificException as e:
    print(f"Operation failed: {e}")
    return False
except Exception as e:
    print(f"Unexpected error: {e}")
    raise
```

### Game Architecture Patterns

#### Component Inheritance
All game objects inherit from BASE_ classes:
- `GameCharacter(BaseCharacter)`
- `GameWeapon(BaseWeapon)`
- `GamePlatform(BasePlatform)`

#### Update Loop Pattern
```python
def update(self, delta_time: float, platforms: list, arena_height: int):
    # Always call parent update first
    super().update(delta_time, platforms, arena_height)

    # Custom logic here
    self.custom_behavior(delta_time)
```

#### Coordinate Systems
- **World coordinates**: Y-axis points UP, [0,0] is bottom-left
- **Screen coordinates**: Y-axis points DOWN, [0,0] is top-left
- Use conversion methods: `self.world_to_screen()` and `self.screen_to_world()`

### Testing Patterns

#### Test Structure
Tests are located in `GameFolder/tests/` and automatically discovered. Base tests run against actual game implementations.

#### Test Results
Test results include:
- `success`: Boolean indicating all tests passed
- `total_tests`: Total number of tests run
- `passed_tests`/`failed_tests`: Counts
- `failures`: List of failed test details with tracebacks

### AI Agent Integration

#### Action Logger
```python
from coding.non_callable_tools.action_logger import action_logger

# Start logging session
action_logger.start_session(visual=True)

# Log custom actions
action_logger.log_action("custom_action", {"param": value})

# End session
action_logger.end_session()
```

#### Model Handlers
```python
from coding.generic_implementation import GenericHandler

handler = GenericHandler(
    thinking_model=True,
    provider="GEMINI",  # or "OPENAI"
    model_name="models/gemini-3-flash-preview",
    api_key=api_key
)
```

### Security Considerations

#### API Keys
- Store API keys encrypted in `__config/settings.json`
- Use `decrypt_api_key()` from BASE_files.BASE_helpers
- Never commit plaintext keys

#### File Operations
- Use version control system for safe file modifications
- Automatic backups created in `__game_backups/`
- Patches stored in `__patches/` with metadata

### Development Workflow

1. **Create backup** before major changes
2. **Run tests** after modifications
3. **Use visual logger** for complex debugging
4. **Save patches** for sharing modifications
5. **Apply patches** to sync changes between players

### Common Pitfalls

- Hardcoding `arena_height` values breaks collision detection
- Setting `health = 0` directly doesn't update `is_alive` flag
- Modifying BASE_ files directly (should inherit instead)
- Not calling `super().update()` in custom components
- Using screen coordinates in physics calculations

### Performance Guidelines

- Use efficient collision detection (provided by BASE_ classes)
- Minimize pygame surface operations in update loops
- Cache expensive calculations when possible
- Use appropriate data structures for game state

This document should be updated as new conventions emerge or commands change.</content>
<parameter name="filePath">/Users/inventure71/VSProjects/GenGame/AGENTS.md