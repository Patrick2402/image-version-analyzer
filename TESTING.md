# Testing Guide for Docker Image Version Analyzer

This document explains how to run tests for the Docker Image Version Analyzer project.

## Overview

The test suite includes unit tests for all major components of the analyzer:

- `test_dockerfile_parser.py` - Tests for Dockerfile parsing functionality
- `test_registry_utils.py` - Tests for registry-related utilities
- `test_version_utils.py` - Tests for version comparison and detection algorithms
- `test_utils.py` - Tests for general utility functions
- `test_image_analyzer.py` - Tests for image analysis logic
- `test_gui.py` - Tests for the graphical user interface (requires PyQt5)

## Running Tests

### Prerequisites

To run the tests, you need:

1. Python 3.6 or higher
2. Required packages:
   ```bash
   pip install packaging
   pip install PyQt5  # Only needed for GUI tests
   ```

### Running All Tests

To run all tests:

```bash
python run_tests.py
```

### Running a Specific Test Module

To run a specific test module:

```bash
python run_tests.py test_dockerfile_parser
```

You can also run a specific test class or method:

```bash
python -m unittest test_dockerfile_parser.TestDockerfileParser
python -m unittest test_dockerfile_parser.TestDockerfileParser.test_extract_single_image
```

## Test Structure

Each test module follows a similar structure:

1. A test class that inherits from `unittest.TestCase`
2. Setup and teardown methods for test fixtures
3. Test methods for individual functionality
4. Mocks for external dependencies

### Mocking

We use Python's `unittest.mock` module to simulate external dependencies, particularly:

- HTTP requests to Docker Hub
- File system operations
- GUI interactions

This allows us to test the code in isolation without needing actual Dockerfiles or internet connections.

## Adding New Tests

When adding new functionality, please add corresponding tests. Follow these guidelines:

1. Create test methods that test a single aspect of functionality
2. Use descriptive method names that indicate what's being tested
3. Use mocks where appropriate to isolate the function being tested
4. Add detailed assertions to verify the expected output

## Test Coverage

To check test coverage, you can use the `coverage` package:

```bash
pip install coverage
coverage run run_tests.py
coverage report
coverage html
```

## Continuous Integration

Tests are automatically run in the CI/CD pipeline. Pull requests will not be accepted if they break existing tests.

## Troubleshooting Common Test Issues

### GUI Tests Failing

If GUI tests are failing, make sure:
1. PyQt5 is properly installed
2. You're not running tests in a headless environment without proper setup

### Mock Issues

If you're seeing issues with mocks:
1. Check that you're patching the correct module path
2. Make sure return values match what the code expects
3. Verify that mock call counts and parameters are as expected