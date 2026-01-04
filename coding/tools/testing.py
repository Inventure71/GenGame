"""
Testing Tools for GenGame Agent

Provides tools for running tests and retrieving results.
These tools are designed to be used by the LLM agent during the testing phase.
"""

import sys
import os
from coding.non_callable_tools.action_logger import action_logger

# Add BASE_components to path so we can import the test framework
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from BASE_components.BASE_tests import run_all_tests as _run_all_tests

def parse_test_results(results: dict) -> dict:
    """
    Parse the test results and return a structured output.
    """
    issues_to_fix = []
    if not results["success"]:
        for failure in results["failures"]:
            issue_to_fix_str = ""
            if failure['test_name']:
                issue_to_fix_str += f"Test: {failure['test_name']}\n"
            if failure['source_file']:
                issue_to_fix_str += f"File: {failure['source_file']}\n"
            if failure['error_msg']:
                issue_to_fix_str += f"Error: {failure['error_msg']}\n"
            if failure['traceback']:
                issue_to_fix_str += f"Traceback:\n{failure['traceback']}\n"
            if failure['duration']:
                issue_to_fix_str += f"Duration: {failure['duration']:.3f}s\n"
            if issue_to_fix_str:
                issues_to_fix.append(issue_to_fix_str)
    else:
        print(f"\n✅ All {results['total_tests']} tests passed!")

    return issues_to_fix

def run_all_tests() -> dict:
    """
    Run all tests (base + custom) and return structured results.
    
    This tool executes:
    1. All base game tests from BASE_tests.py using actual game classes
    2. All custom tests discovered in GameFolder/tests/
    
    The base tests automatically import and test the actual game implementations
    from GameFolder (Character, Platform, Weapon, Projectile classes).
    
    Returns:
        dict: Test results with the following structure:
            {
                "success": bool,  # True if all tests passed
                "total_tests": int,
                "passed_tests": int,
                "failed_tests": int,
                "duration": float,  # Total time in seconds
                "summary": str,  # Human-readable summary
                "failures": [  # List of failed tests
                    {
                        "test_name": str,
                        "source_file": str,
                        "error_msg": str,
                        "traceback": str
                    }
                ]
            }
    
    Example:
        >>> results = run_all_tests()
        >>> print(results["summary"])
        >>> if not results["success"]:
        ...     for failure in results["failures"]:
        ...         print(f"Failed: {failure['test_name']}")
    """
    # Run the actual tests (they will auto-import game classes)
    suite = _run_all_tests(verbose=False)

    # Process and log results
    # Ensure logger is enabled/connected if possible
    if action_logger and not action_logger.visual_enabled:
        # Try to enable it if the server is running (implied by usage)
        action_logger.visual_enabled = True
        # If it wasn't started properly, we might need to ensure connection
        if not action_logger.visual_connected:
             # Basic attempt to connect just in case
             try:
                 action_logger._ensure_server_running()
                 action_logger._start_visual_worker()
             except:
                 pass

    failures = []
    
    # We need to iterate over all tests to log them individually
    # Since BASE_tests returns a TestSuite, we can access _tests
    # But usually a TestResult object is better for this.
    # The _run_all_tests returns a TextTestRunner result object (TestResult)
    # The `suite` variable is actually the TestRunner result, not the suite itself.
    
    # Let's reconstruct individual test results from the result object if possible,
    # or just assume we only have failure info. 
    # Standard unittest.TestResult has .failures and .errors list.
    # It doesn't easily expose passed tests unless we wrap the runner.
    # For now, we'll log failures as "failed" and just log a summary.
    # IMPROVEMENT: To get all tests (pass/fail), we would need a custom TestRunner or Listener.
    # For this iteration, we will send what we have.
    
    pass_count = suite.passed_tests
    fail_count = suite.failed_tests
    
    # Log failures detailed
    for result in suite.results:
        status = "passed" if result.passed else "failed"
        test_data = {
            "test_name": result.test_name,
            "source_file": result.source_file,
            "status": status,
            "duration": result.duration,
            "error_msg": result.error_msg,
            "traceback": result.error_traceback
        }
        if action_logger:
            action_logger.log_test_result(test_data)
            
        if not result.passed:
            failures.append(test_data)
            
    # We can't easily iterate passed tests from the simple result object provided by BASE_tests
    # without modifying BASE_tests.py.
    # However, we can log a summary event.
    
    if action_logger:
        action_logger.log_test_summary({
            "success": suite.all_passed,
            "total": suite.total_tests,
            "passed": pass_count,
            "failed": fail_count,
            "duration": suite.total_duration
        })
    
    # Return tool output format
    return {
        "success": suite.all_passed,
        "total_tests": suite.total_tests,
        "passed_tests": suite.passed_tests,
        "failed_tests": suite.failed_tests,
        "duration": suite.total_duration,
        "summary": suite.get_summary(),
        "failures": failures
    }


def get_test_file_template(feature_name: str) -> str:
    """
    Generate a template for a new test file.
    
    Args:
        feature_name: Name of the feature being tested (e.g., "rocket_launcher")
        
    Returns:
        str: Template code for the test file
        
    Example:
        >>> template = get_test_file_template("double_jump")
        >>> # Use create_file and modify_file_inline to create the test file
    """
    from datetime import datetime
    
    template = f'''"""
Tests for {feature_name.replace('_', ' ').title()}

This module tests the following functionality:
- [TODO: List what this tests]

Created by: GenGame Testing Agent
Date: {datetime.now().strftime("%Y-%m-%d")}
"""

from BASE_components.BASE_character import BaseCharacter
from BASE_components.BASE_weapon import BaseWeapon
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_projectile import BaseProjectile
# Import any custom game components as needed


def test_{feature_name}_basic():
    """Test basic functionality of {feature_name.replace('_', ' ')}."""
    # TODO: Implement test
    # 1. Setup
    # 2. Execute
    # 3. Assert
    pass


def test_{feature_name}_edge_case():
    """Test edge cases for {feature_name.replace('_', ' ')}."""
    # TODO: Implement test
    pass


# Add more test functions as needed
'''
    
    return template


# Export the tools
__all__ = ['run_all_tests', 'get_test_file_template']

