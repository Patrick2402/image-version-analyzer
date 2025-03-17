import unittest
import json
import tempfile
import os
import re
from datetime import datetime
from formatters import (
    BaseFormatter, TextFormatter, JsonFormatter, 
    CsvFormatter, MarkdownFormatter, HtmlFormatter,
    get_formatter
)

class TestBaseFormatter(unittest.TestCase):
    
    def test_get_timestamp(self):
        """Test timestamp generation"""
        formatter = BaseFormatter(include_timestamp=True)
        timestamp = formatter.get_timestamp()
        
        # Verify timestamp format (YYYY-MM-DD HH:MM:SS)
        pattern = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
        self.assertTrue(re.match(pattern, timestamp))
        
        # Verify no timestamp when disabled
        formatter = BaseFormatter(include_timestamp=False)
        self.assertIsNone(formatter.get_timestamp())
    
    def test_get_summary(self):
        """Test summary generation"""
        formatter = BaseFormatter()
        results = [
            {'status': 'OUTDATED', 'image': 'image1'},
            {'status': 'WARNING', 'image': 'image2'},
            {'status': 'UNKNOWN', 'image': 'image3'},
            {'status': 'UP-TO-DATE', 'image': 'image4'},
            {'status': 'OUTDATED', 'image': 'image5'}
        ]
        
        summary = formatter.get_summary(results)
        
        self.assertEqual(summary['total'], 5)
        self.assertEqual(summary['outdated'], 2)
        self.assertEqual(summary['warnings'], 1)
        self.assertEqual(summary['unknown'], 1)
        self.assertEqual(summary['up_to_date'], 1)
        
        # Check image lists
        self.assertEqual(len(summary['outdated_images']), 2)
        self.assertEqual(summary['outdated_images'][0]['image'], 'image1')
        self.assertEqual(summary['outdated_images'][1]['image'], 'image5')
    
    def test_save_to_file(self):
        """Test saving content to file"""
        formatter = BaseFormatter()
        test_content = "Test content"
        
        # Test with temp file
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_output.txt")
            
            # Save content
            result = formatter.save_to_file(test_content, test_file)
            self.assertTrue(result)
            
            # Verify file content
            with open(test_file, 'r') as f:
                content = f.read()
                self.assertEqual(content, test_content)
        
        # Test with invalid path
        result = formatter.save_to_file(test_content, "/path/that/does/not/exist/file.txt")
        self.assertFalse(result)


class TestTextFormatter(unittest.TestCase):
    
    def test_format(self):
        """Test text formatting"""
        formatter = TextFormatter(include_timestamp=False)
        results = [
            {
                'status': 'OUTDATED', 
                'image': 'python:3.9', 
                'message': 'Image is outdated'
            },
            {
                'status': 'UP-TO-DATE', 
                'image': 'node:18', 
                'message': 'Image is up-to-date'
            }
        ]
        
        output = formatter.format(results, 2)
        
        # Check basic elements
        self.assertIn("Found 2 image(s) in Dockerfile:", output)
        self.assertIn("1. python:3.9", output)
        self.assertIn("2. node:18", output)
        self.assertIn("ANALYSIS SUMMARY", output)
        self.assertIn("⛔ 1 OUTDATED IMAGE(S):", output)
        self.assertIn("python:3.9 : Image is outdated", output)
        
        # With timestamp
        formatter = TextFormatter(include_timestamp=True)
        output = formatter.format(results, 2)
        self.assertIn("Analysis Time:", output)


class TestJsonFormatter(unittest.TestCase):
    
    def test_format(self):
        """Test JSON formatting"""
        formatter = JsonFormatter(include_timestamp=False)
        results = [
            {
                'status': 'OUTDATED', 
                'image': 'python:3.9', 
                'current': '3.9',
                'recommended': '3.12',
                'gap': 3,
                'message': 'Image is outdated'
            }
        ]
        
        output = formatter.format(results, 1)
        
        # Parse the JSON to verify
        data = json.loads(output)
        
        self.assertEqual(data['total_images'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['image'], 'python:3.9')
        self.assertEqual(data['results'][0]['status'], 'OUTDATED')
        self.assertEqual(data['summary']['outdated'], 1)
        
        # With timestamp
        formatter = JsonFormatter(include_timestamp=True)
        output = formatter.format(results, 1)
        data = json.loads(output)
        self.assertIn('timestamp', data)


class TestCsvFormatter(unittest.TestCase):
    
    def test_format(self):
        """Test CSV formatting"""
        formatter = CsvFormatter()
        results = [
            {
                'image': 'python:3.9',
                'status': 'OUTDATED',
                'current': '3.9',
                'recommended': '3.12',
                'gap': 3,
                'message': 'Image is outdated'
            },
            {
                'image': 'node:18',
                'status': 'UP-TO-DATE',
                'current': '18',
                'recommended': '18',
                'gap': 0,
                'message': 'Image is up-to-date'
            }
        ]
        
        output = formatter.format(results, 2)
        
        # Check CSV structure
        lines = output.strip().split('\n')
        self.assertEqual(len(lines), 3)  # Header + 2 data rows
        
        # Check header
        self.assertEqual(lines[0], 'image,status,current,recommended,gap,message')
        
        # Check data
        self.assertIn('python:3.9,OUTDATED,3.9,3.12,3,Image is outdated', lines[1])
        self.assertIn('node:18,UP-TO-DATE,18,18,0,Image is up-to-date', lines[2])


class TestMarkdownFormatter(unittest.TestCase):
    
    def test_format(self):
        """Test Markdown formatting"""
        formatter = MarkdownFormatter(include_timestamp=False)
        results = [
            {
                'image': 'python:3.9',
                'status': 'OUTDATED',
                'current': '3.9',
                'recommended': '3.12',
                'gap': 3,
                'message': 'Image is outdated'
            }
        ]
        
        output = formatter.format(results, 1)
        
        # Check Markdown elements
        self.assertIn("# Docker Image Analysis Report", output)
        self.assertIn("## Found 1 image(s)", output)
        self.assertIn("| Image | Status | Current | Recommended | Gap | Message |", output)
        self.assertIn("| `python:3.9` | ⛔ OUTDATED | 3.9 | 3.12 | 3 | Image is outdated |", output)
        
        # With timestamp
        formatter = MarkdownFormatter(include_timestamp=True)
        output = formatter.format(results, 1)
        self.assertIn("*Generated on:", output)


class TestHtmlFormatter(unittest.TestCase):
    
    def test_format(self):
        """Test HTML formatting"""
        formatter = HtmlFormatter(include_timestamp=False)
        results = [
            {
                'image': 'python:3.9',
                'status': 'OUTDATED',
                'current': '3.9',
                'recommended': '3.12',
                'gap': 3,
                'message': 'Image is outdated'
            }
        ]
        
        output = formatter.format(results, 1)
        
        # Check HTML structure
        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("<title>Docker Image Analysis Report</title>", output)
        self.assertIn("<h1>Docker Image Analysis Report</h1>", output)
        self.assertIn("<code>python:3.9</code>", output)
        self.assertIn("OUTDATED", output)
        
        # Check CSS
        self.assertIn("<style>", output)
        
        # With timestamp
        formatter = HtmlFormatter(include_timestamp=True)
        output = formatter.format(results, 1)
        self.assertIn("<em>Generated on:", output)


class TestGetFormatter(unittest.TestCase):
    
    def test_get_formatter(self):
        """Test getting formatters"""
        # Test valid formatters
        self.assertIsInstance(get_formatter('text'), TextFormatter)
        self.assertIsInstance(get_formatter('json'), JsonFormatter)
        self.assertIsInstance(get_formatter('csv'), CsvFormatter)
        self.assertIsInstance(get_formatter('markdown'), MarkdownFormatter)
        self.assertIsInstance(get_formatter('html'), HtmlFormatter)
        
        # Test case insensitivity
        self.assertIsInstance(get_formatter('JSON'), JsonFormatter)
        self.assertIsInstance(get_formatter('Html'), HtmlFormatter)
        
        # Test invalid format (should default to TextFormatter)
        self.assertIsInstance(get_formatter('invalid'), TextFormatter)
        
        # Test timestamp option
        formatter = get_formatter('text', include_timestamp=False)
        self.assertFalse(formatter.include_timestamp)


if __name__ == '__main__':
    unittest.main()