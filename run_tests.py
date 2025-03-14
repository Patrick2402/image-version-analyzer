#!/usr/bin/env python3
import unittest
import sys
import os

def run_all_tests():
    """Run all test modules in the tests directory."""
    # Find all test modules
    test_loader = unittest.TestLoader()
    
    # Option 1: Run tests in current directory
    test_suite = test_loader.discover('.', pattern='test_*.py')
    
    # Option 2: If tests are in a tests directory
    if os.path.exists('tests'):
        tests_dir = os.path.abspath('tests')
        print(f"Discovering tests in: {tests_dir}")
        test_suite = test_loader.discover(tests_dir, pattern='test_*.py')
    
    # Run tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1

def run_specific_test(test_name):
    """Run a specific test module by name."""
    # Import the specified test module
    if test_name.endswith('.py'):
        test_name = test_name[:-3]
    if test_name.startswith('test_'):
        test_name = test_name
    else:
        test_name = f"test_{test_name}"
    
    try:
        # Try to import the module
        __import__(test_name)
        
        # Run the tests in the module
        test_suite = unittest.TestLoader().loadTestsFromName(test_name)
        test_runner = unittest.TextTestRunner(verbosity=2)
        result = test_runner.run(test_suite)
        
        # Return exit code based on test results
        return 0 if result.wasSuccessful() else 1
    except ModuleNotFoundError:
        print(f"Error: Test module '{test_name}' not found.")
        return 1

if __name__ == "__main__":
    # If specific test is specified, run it
    if len(sys.argv) > 1:
        sys.exit(run_specific_test(sys.argv[1]))
    else:
        # Otherwise run all tests
        sys.exit(run_all_tests())