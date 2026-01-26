"""
Core Conflict Test Framework

This module contains:
1. TestRunner - A robust test runner with graceful error handling
2. Base game tests - Tests for core game functionality that must always pass
3. Test discovery - Automatically finds and runs tests from GameFolder/tests/

Usage:
    from BASE_components.BASE_tests import run_all_tests
    results = run_all_tests()
    print(results.get_summary())
"""

import os
import sys
import time
import traceback
import importlib.util
import inspect
from io import StringIO
from contextlib import contextmanager
from typing import List, Callable, Optional, Type, Any
from dataclasses import dataclass, field
from coding.non_callable_tools.helpers import clear_python_cache
from coding.non_callable_tools.action_logger import action_logger
# Set up headless mode for automated testing (only when run directly)
import pygame
from BASE_components.BASE_arena import Arena as BaseArena
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_effects import TimedEffect
from BASE_components.BASE_camera import BaseCamera


# =============================================================================
# TEST RESULT DATA STRUCTURES
# =============================================================================

@dataclass
class TestResult:
    """Result of a single test execution."""
    test_name: str
    passed: bool
    duration: float
    error_msg: Optional[str] = None
    error_traceback: Optional[str] = None
    source_file: str = "BASE_tests.py"
    stdout: str = ""
    
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        duration_str = f"{self.duration:.3f}s"
        result = f"{status} | {self.test_name} ({duration_str})"
        if not self.passed and self.error_msg:
            result += f"\n      Error: {self.error_msg}"
        return result


@dataclass
class TestSuite:
    """Collection of test results with summary statistics."""
    results: List[TestResult] = field(default_factory=list)
    total_duration: float = 0.0
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        self.total_duration += result.duration
    
    @property
    def total_tests(self) -> int:
        return len(self.results)
    
    @property
    def passed_tests(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def failed_tests(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    @property
    def all_passed(self) -> bool:
        return self.failed_tests == 0
    
    def get_failures(self) -> List[TestResult]:
        return [r for r in self.results if not r.passed]
    
    def get_summary(self) -> str:
        """Generate a human-readable summary of test results."""
        lines = []
        lines.append("=" * 70)
        lines.append("TEST RESULTS SUMMARY")
        lines.append("=" * 70)
        lines.append(f"Total Tests: {self.total_tests}")
        lines.append(f"Passed: {self.passed_tests}")
        lines.append(f"Failed: {self.failed_tests}")
        lines.append(f"Total Duration: {self.total_duration:.3f}s")
        lines.append("")
        
        if self.all_passed:
            lines.append("✓ ALL TESTS PASSED! ✓")
        else:
            lines.append("✗ SOME TESTS FAILED ✗")
        
        lines.append("=" * 70)
        lines.append("")
        
        # Group results by source file
        base_results = [r for r in self.results if r.source_file == "BASE_tests.py"]
        custom_results = [r for r in self.results if r.source_file != "BASE_tests.py"]
        
        if base_results:
            lines.append("BASE TESTS:")
            lines.append("-" * 70)
            for result in base_results:
                lines.append(f"  {result}")
            lines.append("")
        
        if custom_results:
            lines.append("CUSTOM TESTS:")
            lines.append("-" * 70)
            for result in custom_results:
                lines.append(f"  {result}")
            lines.append("")
        
        # Show detailed failures
        failures = self.get_failures()
        if failures:
            lines.append("FAILURE DETAILS:")
            lines.append("=" * 70)
            for failure in failures:
                lines.append(f"\nTest: {failure.test_name}")
                lines.append(f"File: {failure.source_file}")
                lines.append(f"Error: {failure.error_msg}")
                if failure.error_traceback:
                    lines.append("Traceback:")
                    lines.append(failure.error_traceback)
                lines.append("-" * 70)
        
        return "\n".join(lines)


# =============================================================================
# STDOUT CAPTURE HELPER
# =============================================================================

@contextmanager
def capture_stdout():
    """Context manager to capture stdout. helper for test execution."""
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    try:
        yield captured_output
    finally:
        sys.stdout = old_stdout


# =============================================================================
# TEST RUNNER
# =============================================================================

class TestRunner:
    """
    Robust test runner that executes tests with graceful error handling.
    
    Features:
    - Catches and logs exceptions without crashing
    - Times each test execution
    - Provides detailed error tracebacks
    - Supports test discovery from multiple sources
    - Isolates test failures (one failure doesn't stop others)
    """
    
    def __init__(self, timeout: float = 10.0):
        """
        Initialize the test runner.
        
        Args:
            timeout: Maximum seconds allowed per test (not yet implemented)
        """
        self.timeout = timeout
        self.pygame_initialized = False
    
    def setup_pygame_headless(self):
        """Initialize pygame in headless mode for testing."""
        if self.pygame_initialized:
            return

        # FIX: Assume pygame is already initialized when running from menu
        # This prevents any pygame API calls from background threads which can cause deadlocks
        try:
            import threading
            if threading.current_thread() != threading.main_thread():
                # We're in a background thread, assume pygame is already set up by main thread
                self.pygame_initialized = True
                print("Pygame already initialized, skipping initialization")
                return
        except:
            pass

        # Only check pygame status from main thread
        if pygame.get_init():
            self.pygame_initialized = True
            print("Pygame already initialized, skipping initialization")
            return

        try:
            # Set headless mode for testing (only if no display exists)
            import os
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            pygame.init()
            # Create a minimal dummy surface
            pygame.display.set_mode((1, 1))
            self.pygame_initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize pygame: {e}")
    
    def run_test_with_args(self, test_func: Callable, args: List[Any], source_file: str = "BASE_tests.py") -> TestResult:
        """
        Run a single test function with arguments.
        
        Args:
            test_func: The test function to execute
            args: List of arguments to pass to the test function
            source_file: Name of the file containing the test
            
        Returns:
            TestResult object with execution details
        """
        test_name = test_func.__name__
        start_time = time.time()
        
        with capture_stdout() as output:
            try:
                # Execute the test with arguments
                test_func(*args)
                duration = time.time() - start_time
                return TestResult(
                    test_name=test_name,
                    passed=True,
                    duration=duration,
                    source_file=source_file,
                    stdout=output.getvalue()
                )
            except AssertionError as e:
                # Test failed with assertion
                duration = time.time() - start_time
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    duration=duration,
                    error_msg=str(e),
                    error_traceback=traceback.format_exc(),
                    source_file=source_file,
                    stdout=output.getvalue()
                )
            except Exception as e:
                # Test crashed with unexpected error
                duration = time.time() - start_time
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    duration=duration,
                    error_msg=f"Unexpected error: {type(e).__name__}: {str(e)}",
                    error_traceback=traceback.format_exc(),
                    source_file=source_file,
                    stdout=output.getvalue()
                )
    
    def run_test(self, test_func: Callable, source_file: str = "BASE_tests.py") -> TestResult:
        """
        Run a single test function with error handling.
        
        Args:
            test_func: The test function to execute
            source_file: Name of the file containing the test
            
        Returns:
            TestResult object with execution details
        """
        test_name = test_func.__name__
        start_time = time.time()
        
        with capture_stdout() as output:
            try:
                # Execute the test
                test_func()
                duration = time.time() - start_time
                return TestResult(
                    test_name=test_name,
                    passed=True,
                    duration=duration,
                    source_file=source_file,
                    stdout=output.getvalue()
                )
            except AssertionError as e:
                # Test failed with assertion
                duration = time.time() - start_time
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    duration=duration,
                    error_msg=str(e),
                    error_traceback=traceback.format_exc(),
                    source_file=source_file,
                    stdout=output.getvalue()
                )
            except Exception as e:
                # Test crashed with unexpected error
                duration = time.time() - start_time
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    duration=duration,
                    error_msg=f"Unexpected error: {type(e).__name__}: {str(e)}",
                    error_traceback=traceback.format_exc(),
                    source_file=source_file,
                    stdout=output.getvalue()
                )
    
    def run_tests(self, test_functions: List[Callable], source_file: str = "BASE_tests.py") -> TestSuite:
        """
        Run a list of test functions.
        
        Args:
            test_functions: List of test functions to execute
            source_file: Name of the file containing the tests
            
        Returns:
            TestSuite with all results
        """
        suite = TestSuite()
        
        for test_func in test_functions:
            result = self.run_test(test_func, source_file)
            suite.add_result(result)
        
        return suite
    
    def discover_tests_in_file(self, file_path: str) -> List[Callable]:
        """
        Discover all test functions in a Python file.
        
        A function is considered a test if:
        - Its name starts with 'test_'
        - It takes no arguments
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of test functions
        """
        test_functions = []
        
        try:
            # Load the module dynamically
            module_name = os.path.splitext(os.path.basename(file_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find all test functions
                for name, obj in inspect.getmembers(module):
                    if (callable(obj) and 
                        name.startswith('test_') and 
                        inspect.isfunction(obj)):
                        # Check if function takes no arguments (except self for methods)
                        sig = inspect.signature(obj)
                        if len(sig.parameters) == 0:
                            test_functions.append(obj)
        except Exception as e:
            # Don't just print and return empty - we need to track this failure
            # The error will be handled by discover_tests_in_directory
            raise  # Re-raise so discover_tests_in_directory can handle it
        
        return test_functions
    
    def discover_tests_in_directory(self, directory: str) -> dict:
        """
        Discover all test files in a directory.
        
        Args:
            directory: Path to the directory to search
            
        Returns:
            Dictionary mapping file paths to lists of test functions
        """
        discovered = {}
        
        if not os.path.exists(directory):
            return discovered
        
        for filename in os.listdir(directory):
            if filename.endswith('.py') and not filename.startswith('__'):
                file_path = os.path.join(directory, filename)
                try:
                    test_functions = self.discover_tests_in_file(file_path)
                    if test_functions:
                        discovered[file_path] = test_functions
                except Exception as e:
                    # Track import failures - create a synthetic test result
                    # Store the error info so we can create a TestResult later
                    error_msg = str(e)
                    error_traceback = traceback.format_exc()
                    # Store as a special marker that indicates import failure
                    discovered[file_path] = {
                        '_import_error': True,
                        'error_msg': error_msg,
                        'error_traceback': error_traceback
                    }
        
        return discovered


# =============================================================================
# BASE GAME TESTS - Accept classes as arguments
# =============================================================================

def test_character_creation(character_class: Type):
    """Test that a character can be created with basic properties."""
    char = character_class(
        name="Test Player",
        description="A test character",
        image="",
        location=[100.0, 100.0],
        width=50,
        height=50
    )
    
    assert char.name == "Test Player", "Character name not set correctly"
    assert char.location == [100.0, 100.0], "Character location not set correctly"
    assert char.width == 50, "Character width not set correctly"
    assert char.height == 50, "Character height not set correctly"
    assert char.lives == char.MAX_LIVES, "Character should start with MAX_LIVES"
    assert not char.is_eliminated, "Character should not be eliminated initially"


def test_character_movement_bounds(character_class: Type):
    """Test that a character moves via process_input and respects arena bounds."""
    arena = BaseArena(width=300, height=200, headless=True)
    char = character_class(
        name="Test Player",
        description="Test",
        image="",
        location=[150.0, 100.0],
        width=30,
        height=30,
    )
    arena.add_character(char)

    input_data = {"movement": [1, 0], "mouse_pos": [0.0, 0.0]}
    char.process_input(input_data, arena)
    assert char.location[0] > 150.0, "Character should move right"

    input_data = {"movement": [-1, 0], "mouse_pos": [0.0, 0.0]}
    char.process_input(input_data, arena)
    assert 0.0 < char.location[0] < arena.width, "Character should remain within horizontal bounds"


def test_character_max_lives(character_class: Type):
    """Test that characters start with MAX_LIVES."""
    char = character_class(
        name="Test Player",
        description="Test",
        image="",
        location=[100.0, 100.0]
    )

    assert char.lives == char.MAX_LIVES, "Character should start with MAX_LIVES"


def test_character_take_damage(character_class: Type):
    """Test that a character can take damage and lose health."""
    char = character_class(
        name="Test Player",
        description="Test",
        image="",
        location=[100.0, 100.0]
    )

    initial_health = char.health
    char.take_damage(20)
    assert char.health < initial_health, "Health should decrease after taking damage"


def test_character_death_and_respawn(character_class: Type):
    """Test that a character loses a life and can respawn if not eliminated."""
    char = character_class(
        name="Test Player",
        description="Test",
        image="",
        location=[100.0, 100.0]
    )

    char.lives = 2
    initial_lives = char.lives
    char.take_damage(char.health + 10)

    assert not char.is_alive, "Character should be dead after lethal damage"
    assert char.lives == initial_lives - 1, "Character should lose one life"
    assert not char.is_eliminated, "Character should not be eliminated with lives remaining"

    char.respawn([120.0, 120.0])
    assert char.is_alive, "Character should be alive after respawn"
    assert char.health == char.max_health, "Character should respawn with full health"
    assert char.location == [120.0, 120.0], "Character should respawn at the provided location"


def test_character_elimination(character_class: Type):
    """Test that a character is eliminated when all lives are lost."""
    char = character_class(
        name="Test Player",
        description="Test",
        image="",
        location=[100.0, 100.0]
    )
    
    # Lose all lives
    char.lives = 0
    char.is_eliminated = True
    
    assert char.is_eliminated, "Character should be eliminated with 0 lives"


def test_platform_creation(platform_class: Type):
    """Test that a platform can be created."""
    platform = platform_class(x=100, y=200, width=300, height=20)
    
    assert platform.rect.x == 100, "Platform x position not set"
    assert platform.rect.y == 200, "Platform y position not set"
    assert platform.rect.width == 300, "Platform width not set"
    assert platform.rect.height == 20, "Platform height not set"


def test_character_input_keybinds(character_class: Type):
    """Test that get_input_data includes movement + mouse_pos (base schema)."""
    import pygame
    
    mouse_pos = [100.0, 200.0]
    mouse_buttons = [False, False, False]  # Left, Middle, Right

    # No keys, no mouse
    held_keys = set()
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    
    if "mouse_pos" not in input_data:
        print(
            "DEBUG test_character_input_keybinds: 'mouse_pos' missing from input_data.\n"
            "Possible cause: Character.get_input_data was overridden and no longer includes "
            "'mouse_pos'.\n"
            f"Got keys: {list(input_data.keys())}"
        )
    assert input_data["mouse_pos"] == mouse_pos, "mouse_pos should always be present"
    
    if "movement" not in input_data:
        print(
            "DEBUG test_character_input_keybinds: 'movement' missing from input_data.\n"
            "Possible cause: Character.get_input_data is still using the GAME schema "
            "with 'move' / 'jump' instead of BASE 'movement'.\n"
            "Expected BASE schema: 'movement' plus 'mouse_pos'.\n"
            f"Got keys: {list(input_data.keys())}"
        )
    assert input_data["movement"] == [0, 0], "No movement when no keys pressed (BASE schema uses 'movement', not 'move')"
    
    # Movement keys
    held_keys = {pygame.K_a}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"][0] == -1, "Should move left when A is pressed"
    
    held_keys = {pygame.K_d}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"][0] == 1, "Should move right when D is pressed"
    
    held_keys = {pygame.K_w}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"][1] == 1, "Should move up when W is pressed"
    
    held_keys = {pygame.K_s}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"][1] == -1, "Should move down when S is pressed"
    
    # Arrow keys (alternative keybinds)
    held_keys = {pygame.K_LEFT}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"][0] == -1, "Should move left when LEFT arrow is pressed"
    
    held_keys = {pygame.K_RIGHT}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"][0] == 1, "Should move right when RIGHT arrow is pressed"
    
    # Multiple keys simultaneously
    held_keys = {pygame.K_d, pygame.K_w}
    input_data = character_class.get_input_data(held_keys, mouse_buttons, mouse_pos)
    assert input_data["movement"] == [1, 1], "Should combine movement directions"


def test_timed_effect_expiration():
    """Test that TimedEffect expires after its lifetime."""
    effect = TimedEffect([50.0, 50.0], lifetime=0.5)
    expired = effect.update(0.2)
    assert not expired, "Effect should not be expired yet"
    expired = effect.update(0.4)
    assert expired, "Effect should expire after lifetime"


def test_safe_zone_damage(character_class: Type):
    """Test that the safe zone damages characters outside its radius."""
    arena = BaseArena(width=200, height=200, headless=True)
    arena.safe_damage_interval = 0.0
    arena.safe_zone.center = [0.0, 0.0]
    arena.safe_zone.target_center = [0.0, 0.0]
    arena.safe_zone.radius = 10.0

    char = character_class(
        name="Test Player",
        description="Test",
        image="",
        location=[150.0, 150.0],
        width=30,
        height=30,
    )
    arena.add_character(char)

    initial_health = char.health
    arena.update(0.1)
    assert char.health < initial_health, "Character should take safe zone damage outside radius"


def test_camera_world_screen_roundtrip():
    """Test camera world/screen conversion roundtrip."""
    camera = BaseCamera(world_width=2000, world_height=1500, view_width=400, view_height=300)
    camera.set_center(1000, 750)

    screen_x, screen_y = camera.world_to_screen_point(1000, 750)
    world_x, world_y = camera.screen_to_world_point(screen_x, screen_y)

    assert abs(world_x - 1000) < 0.01
    assert abs(world_y - 750) < 0.01


# =============================================================================
# MAIN TEST EXECUTION FUNCTIONS
# =============================================================================

def get_base_test_functions() -> List[tuple]:
    """
    Get all base test functions with their required parameters.
    
    Returns:
        List of tuples: (test_function, param_name, description)
    """
    return [
        (test_character_creation, "character_class", "Character class to test"),
        (test_character_movement_bounds, "character_class", "Character movement in arena bounds"),
        (test_character_max_lives, "character_class", "Character class to test"),
        (test_character_take_damage, "character_class", "Character class to test"),
        (test_character_death_and_respawn, "character_class", "Character class to test"),
        (test_character_elimination, "character_class", "Character class to test"),
        (test_character_input_keybinds, "character_class", "Character input keybinds (set format)"),
        (test_platform_creation, "platform_class", "Platform class to test"),
        (test_timed_effect_expiration, None, "TimedEffect expiration"),
        (test_safe_zone_damage, "character_class", "Safe zone damage ticks"),
        (test_camera_world_screen_roundtrip, None, "Camera world/screen roundtrip"),
    ]


def run_all_tests(
    character_class: Type = None,
    platform_class: Type = None,
    verbose: bool = True
) -> TestSuite:
    """
    Run all tests: base tests + custom tests from GameFolder/tests.
    
    This is the main entry point for the testing system.
    
    Args:
        character_class: The Character class to test (from GameFolder/characters/)
        platform_class: The Platform class to test (from BASE_components or GameFolder)
        verbose: If True, print progress messages
        
    Returns:
        TestSuite with all test results
    """
    # Clear cache to ensure tests run against latest code
    # clear_python_cache() is now thread-safe - it checks pygame initialization
    # and skips gc.collect() from background threads to avoid deadlocks
    clear_python_cache()

    time.sleep(1)

    runner = TestRunner()
    runner.setup_pygame_headless()

    combined_suite = TestSuite()
    
    # If no classes provided, try to import from GameFolder
    if character_class is None:
        try:
            from GameFolder.characters.GAME_character import Character
            character_class = Character
        except ImportError:
            if verbose:
                print("Warning: Could not import Character from GameFolder")

    if platform_class is None:
        platform_class = BasePlatform
    
    # Map parameter names to classes
    class_map = {
        "character_class": character_class,
        "platform_class": platform_class,
    }
    
    # 1. Run base tests
    if verbose:
        print("\n" + "=" * 70)
        print("Running BASE TESTS...")
        print("=" * 70)
    
    base_tests = get_base_test_functions()
    if verbose:
        print(f"Found {len(base_tests)} base tests")
    
    passed = 0
    for test_func, param_name, description in base_tests:
        if param_name is None:
            result = runner.run_test(test_func, "BASE_tests.py")
        else:
            required_class = class_map.get(param_name)
            if required_class is None:
                result = TestResult(
                    test_name=test_func.__name__,
                    passed=False,
                    duration=0.0,
                    error_msg=f"Required class '{param_name}' not available",
                    source_file="BASE_tests.py"
                )
            else:
                result = runner.run_test_with_args(test_func, [required_class], "BASE_tests.py")
        
        # Log individual test result to visual logger
        if hasattr(action_logger, 'log_test_result'):
            action_logger.log_test_result({
                'test_name': result.test_name,
                'status': 'passed' if result.passed else 'failed',
                'source_file': result.source_file,
                'error_msg': result.error_msg,
                'traceback': result.error_traceback,
                'duration': result.duration
            })

        combined_suite.add_result(result)
        if result.passed:
            passed += 1
    
    if verbose:
        print(f"Base tests completed: {passed}/{len(base_tests)} passed\n")
    
    # 2. Discover and run custom tests from GameFolder/tests
    tests_dir = "GameFolder/tests"
    if os.path.exists(tests_dir):
        if verbose:
            print("=" * 70)
            print("Running CUSTOM TESTS from GameFolder/tests...")
            print("=" * 70)
        
        discovered = runner.discover_tests_in_directory(tests_dir)
        
        if discovered:
            for file_path, test_data in discovered.items():
                file_name = os.path.basename(file_path)
                
                # Check if this is an import error marker
                if isinstance(test_data, dict) and test_data.get('_import_error'):
                    # Create a synthetic test result for the import failure
                    import_error_result = TestResult(
                        test_name=f"Import Error: {file_name}",
                        passed=False,
                        duration=0.0,
                        error_msg=test_data['error_msg'],
                        error_traceback=test_data['error_traceback'],
                        source_file=file_name
                    )
                    # Log to action_logger for consistency
                    if hasattr(action_logger, 'log_test_result'):
                        action_logger.log_test_result({
                            'test_name': import_error_result.test_name,
                            'status': 'failed',
                            'source_file': import_error_result.source_file,
                            'error_msg': import_error_result.error_msg,
                            'traceback': import_error_result.error_traceback,
                            'duration': import_error_result.duration
                        })
                    combined_suite.add_result(import_error_result)
                    if verbose:
                        print(f"\n✗ Failed to import {file_name}: {test_data['error_msg']}")
                    continue
                
                # Normal test discovery path
                test_functions = test_data
                if verbose:
                    print(f"\nFound {len(test_functions)} tests in {file_name}")
                
                # Custom tests don't take arguments
                custom_suite = runner.run_tests(test_functions, file_name)
                for result in custom_suite.results:
                    if hasattr(action_logger, 'log_test_result'):
                        action_logger.log_test_result({
                            'test_name': result.test_name,
                            'status': 'passed' if result.passed else 'failed',
                            'source_file': result.source_file,
                            'error_msg': result.error_msg,
                            'traceback': result.error_traceback,
                            'duration': result.duration
                        })
                    combined_suite.add_result(result)
                
                if verbose:
                    print(f"{file_name} completed: {custom_suite.passed_tests}/{custom_suite.total_tests} passed")
        else:
            if verbose:
                print("No custom test files found")
    else:
        if verbose:
            print(f"\nNote: Directory '{tests_dir}' does not exist (no custom tests)")
    
    if verbose:
        print("\n" + combined_suite.get_summary())
    
    return combined_suite


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    print("\n🧪 Core Conflict Test Framework")
    print("=" * 70)
    
    results = run_all_tests(verbose=True)
    
    # Exit with appropriate code
    sys.exit(0 if results.all_passed else 1)
