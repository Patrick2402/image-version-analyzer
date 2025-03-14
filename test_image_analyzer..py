import unittest
from unittest.mock import patch, MagicMock
from image_analyzer import analyze_image_tags

class TestImageAnalyzer(unittest.TestCase):
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    def test_analyze_unsupported_registry(self, mock_is_supported, mock_get_tags):
        """Test analyzing an image from an unsupported registry"""
        # Setup mocks
        mock_is_supported.return_value = (False, "gcr.io")
        mock_get_tags.return_value = ([], None)
        
        # Test
        result = analyze_image_tags("gcr.io/project/image:tag", 1, 1, 3)
        
        # Assertions
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['image'], "gcr.io/project/image:tag")
        self.assertEqual(result['message'], "Registry gcr.io not supported")
        mock_is_supported.assert_called_once_with("gcr.io/project/image:tag")
        mock_get_tags.assert_not_called()
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    def test_analyze_no_tags_found(self, mock_is_supported, mock_get_tags):
        """Test analyzing an image with no tags available"""
        # Setup mocks
        mock_is_supported.return_value = (True, None)
        mock_get_tags.return_value = ([], None)
        
        # Test
        result = analyze_image_tags("unknown/image:tag", 1, 1, 3)
        
        # Assertions
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['message'], "No tags found or repository not accessible")
        mock_is_supported.assert_called_once_with("unknown/image:tag")
        mock_get_tags.assert_called_once()
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    @patch('image_analyzer.detect_version_level')
    @patch('image_analyzer.get_public_image_name')
    @patch('image_analyzer.calculate_version_gap')
    def test_analyze_outdated_image(self, mock_calc_gap, mock_get_public, 
                                   mock_detect_level, mock_is_supported, mock_get_tags):
        """Test analyzing an outdated image"""
        # Setup mocks
        mock_is_supported.return_value = (True, None)
        mock_get_tags.return_value = (["1.0.0", "2.0.0", "3.0.0"], "3.0.0")
        mock_get_public.return_value = "python:1.0.0"
        mock_detect_level.return_value = 1
        mock_calc_gap.return_value = (2, ["2.0.0", "3.0.0"])
        
        # Test
        result = analyze_image_tags("python:1.0.0", 1, 1, 1)  # threshold=1
        
        # Assertions
        self.assertEqual(result['status'], 'OUTDATED')
        self.assertEqual(result['gap'], 2)
        self.assertEqual(result['current'], "1.0.0")
        self.assertEqual(result['recommended'], "3.0.0")
        self.assertEqual(result['message'], "Image is 2 major version(s) behind")
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    @patch('image_analyzer.detect_version_level')
    @patch('image_analyzer.get_public_image_name')
    @patch('image_analyzer.calculate_version_gap')
    def test_analyze_up_to_date_image(self, mock_calc_gap, mock_get_public, 
                                     mock_detect_level, mock_is_supported, mock_get_tags):
        """Test analyzing an up-to-date image"""
        # Setup mocks
        mock_is_supported.return_value = (True, None)
        mock_get_tags.return_value = (["1.0.0", "2.0.0", "3.0.0"], "3.0.0")
        mock_get_public.return_value = "python:3.0.0"
        mock_detect_level.return_value = 1
        mock_calc_gap.return_value = (0, [])
        
        # Test
        result = analyze_image_tags("python:3.0.0", 1, 1, 3)
        
        # Assertions
        self.assertEqual(result['status'], 'UP-TO-DATE')
        self.assertEqual(result['gap'], 0)
        self.assertEqual(result['current'], "3.0.0")
        self.assertEqual(result['recommended'], "3.0.0")
        self.assertEqual(result['message'], "Image is up-to-date")
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    @patch('image_analyzer.detect_version_level')
    @patch('image_analyzer.get_public_image_name')
    @patch('image_analyzer.calculate_version_gap')
    def test_analyze_within_threshold(self, mock_calc_gap, mock_get_public, 
                                    mock_detect_level, mock_is_supported, mock_get_tags):
        """Test analyzing an image behind but within threshold"""
        # Setup mocks
        mock_is_supported.return_value = (True, None)
        mock_get_tags.return_value = (["1.0.0", "2.0.0", "3.0.0"], "3.0.0")
        mock_get_public.return_value = "python:2.0.0"
        mock_detect_level.return_value = 1
        mock_calc_gap.return_value = (1, ["3.0.0"])
        
        # Test
        result = analyze_image_tags("python:2.0.0", 1, 1, 3)  # threshold=3
        
        # Assertions
        self.assertEqual(result['status'], 'UP-TO-DATE')
        self.assertEqual(result['gap'], 1)
        self.assertEqual(result['current'], "2.0.0")
        self.assertEqual(result['recommended'], "3.0.0")
        self.assertEqual(result['message'], "Image is 1 major version(s) behind but within threshold (3)")
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    @patch('image_analyzer.get_public_image_name')
    def test_analyze_no_explicit_tag(self, mock_get_public, mock_is_supported, mock_get_tags):
        """Test analyzing an image with no explicit tag (using 'latest')"""
        # Setup mocks
        mock_is_supported.return_value = (True, None)
        mock_get_tags.return_value = (["1.0.0", "2.0.0", "3.0.0", "latest"], "3.0.0")
        mock_get_public.return_value = "python"  # No tag
        
        # Test
        result = analyze_image_tags("python", 1, 1, 3)
        
        # Assertions
        self.assertEqual(result['status'], 'WARNING')
        self.assertIsNone(result['gap'])
        self.assertEqual(result['message'], "No explicit tag specified (using 'latest')")
    
    @patch('image_analyzer.get_image_tags')
    @patch('image_analyzer.is_supported_registry')
    @patch('image_analyzer.detect_version_level')
    @patch('image_analyzer.get_public_image_name')
    @patch('image_analyzer.calculate_version_gap')
    @patch('image_analyzer.check_lts_version')
    def test_analyze_lts_violation(self, mock_check_lts, mock_calc_gap, mock_get_public, 
                                 mock_detect_level, mock_is_supported, mock_get_tags):
        """Test analyzing an image with LTS policy violation"""
        # Setup mocks
        mock_is_supported.return_value = (True, None)
        mock_get_tags.return_value = (["16", "17", "18", "19"], "19")
        mock_get_public.return_value = "node:16"
        mock_detect_level.return_value = 1
        mock_calc_gap.return_value = (3, ["17", "18", "19"])
        mock_check_lts.return_value = False  # LTS violation
        
        # Custom rules with LTS versions
        custom_rules = {
            "node": {
                "lts_versions": [16, 18, 20]
            }
        }
        
        # Test
        result = analyze_image_tags("node:16", 1, 1, 1, None, None, custom_rules)  # threshold=1
        
        # Assertions
        self.assertEqual(result['status'], 'WARNING')
        self.assertEqual(result['gap'], 3)
        self.assertEqual(result['current'], "16")
        self.assertEqual(result['recommended'], "19")
        self.assertEqual(result['message'], "Image is 3 major version(s) behind but violates LTS policy")


if __name__ == "__main__":
    unittest.main()