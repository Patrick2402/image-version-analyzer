import unittest
from version_utils import (
    check_lts_version,
    calculate_version_gap,
    detect_version_level
)


class TestVersionUtils(unittest.TestCase):
    
    def test_check_lts_version(self):
        """Test checking LTS version rules"""
        # Setup custom rules
        custom_rules = {
            "node": {
                "lts_versions": [16, 18, 20, 22]
            }
        }
        
        # Same LTS to same LTS
        self.assertTrue(check_lts_version("16", "16", custom_rules, "node"))
        
        # LTS to newer LTS (valid)
        self.assertTrue(check_lts_version("16", "18", custom_rules, "node"))
        self.assertTrue(check_lts_version("18", "20", custom_rules, "node"))
        
        # LTS to non-LTS (invalid)
        self.assertFalse(check_lts_version("16", "17", custom_rules, "node"))
        self.assertFalse(check_lts_version("18", "19", custom_rules, "node"))
        
        # Non-LTS to any (valid)
        self.assertTrue(check_lts_version("17", "18", custom_rules, "node"))
        self.assertTrue(check_lts_version("17", "19", custom_rules, "node"))
        
        # No LTS rule defined
        self.assertTrue(check_lts_version("3.9", "3.10", {}, "python"))
        self.assertTrue(check_lts_version("3.9", "3.10", custom_rules, "python"))
    
    def test_calculate_version_gap(self):
        """Test calculation of version gaps"""
        # Major version gap (level 1)
        result = calculate_version_gap("2.0.0", "4.0.0", 1)
        self.assertEqual(result[0], 2)  # Gap of 2 major versions
        self.assertEqual(set(result[1]), {"3", "4"})  # Missing versions
        
        # Minor version gap (level 2)
        result = calculate_version_gap("2.1.0", "2.4.0", 2)
        self.assertEqual(result[0], 3)  # Gap of 3 minor versions
        self.assertEqual(set(result[1]), {"2.2", "2.3", "2.4"})  # Missing versions
        
        # Patch version gap (level 3)
        result = calculate_version_gap("2.1.1", "2.1.3", 3)
        self.assertEqual(result[0], 2)  # Gap of 2 patch versions
        self.assertEqual(set(result[1]), {"2.1.2", "2.1.3"})  # Missing versions
        
        # With 'v' prefix
        result = calculate_version_gap("v2.0.0", "v4.0.0", 1)
        self.assertEqual(result[0], 2)
        self.assertEqual(set(result[1]), {"v3", "v4"})
        
        # With version variant
        result = calculate_version_gap("2.0.0-alpine", "4.0.0-alpine", 1)
        self.assertEqual(result[0], 2)
        
        # Equal versions
        result = calculate_version_gap("2.0.0", "2.0.0", 1)
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1], [])
        
        # Skip versions using custom rules
        custom_rules = {
            "node": {
                "skip_versions": ["19", "21", "23"]
            }
        }
        result = calculate_version_gap("18", "22", 1, custom_rules, "node")
        self.assertEqual(result[0], 2)  # Gap of 2 versions (20, 22)
        self.assertEqual(set(result[1]), {"20", "22"})  # Only even versions
        
        # Step by rule
        custom_rules = {
            "node": {
                "step_by": 2
            }
        }
        result = calculate_version_gap("18", "22", 1, custom_rules, "node")
        self.assertEqual(result[0], 2)  # 2 steps (18→20→22)
    
    def test_detect_version_level(self):
        """Test automatic detection of version level"""
        # Test with known images (should use predefined level)
        self.assertEqual(detect_version_level(["1.0", "2.0"], "debian", {}), 1)
        self.assertEqual(detect_version_level(["3.15", "3.16", "3.17"], "alpine", {}), 2)
        
        # Test with custom rules (should override defaults)
        custom_rules = {
            "debian": {"level": 2},
            "alpine": {"level": 1}
        }
        self.assertEqual(detect_version_level(["1.0", "2.0"], "debian", custom_rules), 2)
        self.assertEqual(detect_version_level(["3.15", "3.16", "3.17"], "alpine", custom_rules), 1)
        
        # Test pattern analysis with major version changes
        tags = ["1.0.0", "2.0.0", "3.0.0", "4.0.0"]
        self.assertEqual(detect_version_level(tags, "unknown", {}), 1)
        
        # Test pattern analysis with minor version changes
        tags = ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]
        self.assertEqual(detect_version_level(tags, "unknown", {}), 2)
        
        # Test empty tags list
        self.assertEqual(detect_version_level([], "unknown", {}), 1)  # Default
        
        # Test no version tags
        self.assertEqual(detect_version_level(["latest", "stable", "alpine"], "unknown", {}), 1)


if __name__ == "__main__":
    unittest.main()