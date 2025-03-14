import unittest
import os
import tempfile
from image_ignore import ImageIgnoreManager, parse_ignore_options

class TestImageIgnoreManager(unittest.TestCase):
    
    def setUp(self):
        """Create a test manager and temporary directory for test files"""
        self.manager = ImageIgnoreManager()
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary files"""
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)
    
    def test_add_pattern(self):
        """Test adding patterns to the manager"""
        self.manager.add_pattern("python:3.9*")
        self.assertEqual(len(self.manager.patterns), 1)
        self.assertEqual(self.manager.patterns[0], "python:3.9*")
        
        # Adding empty pattern should be ignored
        self.manager.add_pattern("")
        self.assertEqual(len(self.manager.patterns), 1)
        
        # Adding whitespace pattern should be ignored
        self.manager.add_pattern("   ")
        self.assertEqual(len(self.manager.patterns), 1)
        
        # Test whitespace is stripped
        self.manager.add_pattern("  node:16  ")
        self.assertEqual(len(self.manager.patterns), 2)
        self.assertEqual(self.manager.patterns[1], "node:16")
    
    def test_add_patterns_from_list(self):
        """Test adding patterns from a list"""
        patterns = ["python:3.9*", "node:16", "nginx:*"]
        self.manager.add_patterns_from_list(patterns)
        self.assertEqual(len(self.manager.patterns), 3)
        self.assertEqual(self.manager.patterns, patterns)
        
        # Test with empty list
        self.manager = ImageIgnoreManager()
        self.manager.add_patterns_from_list([])
        self.assertEqual(len(self.manager.patterns), 0)
        
        # Test with None
        self.manager.add_patterns_from_list(None)
        self.assertEqual(len(self.manager.patterns), 0)
    
    def test_load_patterns_from_file(self):
        """Test loading patterns from a file"""
        # Create a test file
        file_path = os.path.join(self.test_dir, "ignore.txt")
        with open(file_path, 'w') as f:
            f.write("# This is a comment\n")
            f.write("python:3.9*\n")
            f.write("\n")  # Empty line
            f.write("node:16\n")
            f.write("  nginx:*  \n")  # With whitespace
        
        # Load patterns
        result = self.manager.load_patterns_from_file(file_path)
        self.assertTrue(result)
        self.assertEqual(len(self.manager.patterns), 3)
        self.assertEqual(self.manager.patterns[0], "python:3.9*")
        self.assertEqual(self.manager.patterns[1], "node:16")
        self.assertEqual(self.manager.patterns[2], "nginx:*")
        
        # Test with non-existent file
        self.manager = ImageIgnoreManager()
        result = self.manager.load_patterns_from_file("/path/to/nonexistent/file")
        self.assertFalse(result)
        self.assertEqual(len(self.manager.patterns), 0)
    
    def test_should_ignore(self):
        """Test checking if images should be ignored"""
        # Add some patterns
        self.manager.add_patterns_from_list([
            "python:3.9*",
            "node:16",
            "regex:^debian:(?!11).*"  # Match debian versions except 11
        ])
        
        # Test matching
        self.assertTrue(self.manager.should_ignore("python:3.9-alpine"))
        self.assertTrue(self.manager.should_ignore("python:3.9.6"))
        self.assertTrue(self.manager.should_ignore("node:16"))
        self.assertFalse(self.manager.should_ignore("node:18"))
        self.assertFalse(self.manager.should_ignore("python:3.10"))
        
        # Test regex pattern
        self.assertTrue(self.manager.should_ignore("debian:10"))
        self.assertFalse(self.manager.should_ignore("debian:11"))
        
        # Test with no patterns
        self.manager = ImageIgnoreManager()
        self.assertFalse(self.manager.should_ignore("python:3.9"))
        
        # Test with invalid regex
        self.manager.add_pattern("regex:[invalid")
        self.assertFalse(self.manager.should_ignore("anything"))  # Should not crash
    
    def test_get_patterns(self):
        """Test getting the current patterns"""
        patterns = ["python:3.9*", "node:16"]
        self.manager.add_patterns_from_list(patterns)
        
        # Get patterns
        result = self.manager.get_patterns()
        self.assertEqual(result, patterns)
        
        # Verify that changing the result doesn't affect the original
        result.append("something-else")
        self.assertEqual(len(self.manager.patterns), 2)
        self.assertEqual(self.manager.patterns, patterns)


class TestParseIgnoreOptions(unittest.TestCase):
    
    def setUp(self):
        """Create a temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary files"""
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)
    
    def test_parse_ignore_options(self):
        """Test parsing ignore options from command line args"""
        # Create a test file
        file_path = os.path.join(self.test_dir, "ignore.txt")
        with open(file_path, 'w') as f:
            f.write("python:3.9*\n")
            f.write("node:16\n")
        
        # Test with --ignore flags
        args = ["main.py", "Dockerfile", "--ignore", "nginx:*", "--ignore", "debian:*"]
        manager = parse_ignore_options(args)
        self.assertEqual(len(manager.patterns), 2)
        self.assertEqual(manager.patterns[0], "nginx:*")
        self.assertEqual(manager.patterns[1], "debian:*")
        
        # Test with --ignore-images flag
        args = ["main.py", "Dockerfile", "--ignore-images", file_path]
        manager = parse_ignore_options(args)
        self.assertEqual(len(manager.patterns), 2)
        self.assertEqual(manager.patterns[0], "python:3.9*")
        self.assertEqual(manager.patterns[1], "node:16")
        
        # Test with both flags
        args = ["main.py", "Dockerfile", "--ignore", "nginx:*", "--ignore-images", file_path]
        manager = parse_ignore_options(args)
        self.assertEqual(len(manager.patterns), 3)
        self.assertEqual(manager.patterns[0], "nginx:*")
        self.assertEqual(manager.patterns[1], "python:3.9*")
        self.assertEqual(manager.patterns[2], "node:16")
        
        # Test with missing value for --ignore
        args = ["main.py", "Dockerfile", "--ignore"]
        manager = parse_ignore_options(args)
        self.assertEqual(len(manager.patterns), 0)
        
        # Test with missing value for --ignore-images
        args = ["main.py", "Dockerfile", "--ignore-images"]
        manager = parse_ignore_options(args)
        self.assertEqual(len(manager.patterns), 0)
        
        # Test with non-existent file
        args = ["main.py", "Dockerfile", "--ignore-images", "/path/to/nonexistent/file"]
        manager = parse_ignore_options(args)
        self.assertEqual(len(manager.patterns), 0)


if __name__ == "__main__":
    unittest.main()