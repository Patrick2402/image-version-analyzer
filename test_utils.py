import unittest
import os
import tempfile
from utils import parse_private_registries, load_custom_rules

class TestUtils(unittest.TestCase):
    
    def setUp(self):
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up temporary files
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)
    
    def test_parse_private_registries(self):
        """Test parsing private registry arguments"""
        # No private registry
        args = ["main.py", "Dockerfile", "--tags"]
        result = parse_private_registries(args)
        self.assertEqual(result, [])
        
        # Single private registry
        args = ["main.py", "Dockerfile", "--tags", "--private-registry", "registry.example.com"]
        result = parse_private_registries(args)
        self.assertEqual(result, ["registry.example.com"])
        
        # Private registry file
        registry_file = os.path.join(self.test_dir, "registries.txt")
        with open(registry_file, "w") as f:
            f.write("registry1.example.com\n")
            f.write("registry2.example.com\n")
            f.write("# Comment line\n")
            f.write("registry3.example.com:5000\n")
        
        args = ["main.py", "Dockerfile", "--tags", "--private-registries-file", registry_file]
        result = parse_private_registries(args)
        self.assertEqual(set(result), {"registry1.example.com", "registry2.example.com", "registry3.example.com:5000"})
        
        # Both single registry and file
        args = ["main.py", "Dockerfile", "--tags", "--private-registry", "registry.example.com", 
                "--private-registries-file", registry_file]
        result = parse_private_registries(args)
        self.assertEqual(set(result), {"registry.example.com", "registry1.example.com", 
                                     "registry2.example.com", "registry3.example.com:5000"})
        
        # Private registry flag without value (should use default)
        args = ["main.py", "Dockerfile", "--tags", "--private-registry"]
        result = parse_private_registries(args)
        self.assertEqual(result, ["docker-registry.gitlab:4567"])
    
    def test_load_custom_rules(self):
        """Test loading custom rules from JSON file"""
        # Valid rules file
        rules_file = os.path.join(self.test_dir, "rules.json")
        with open(rules_file, "w") as f:
            f.write("""
            {
                "node": {
                    "level": 1,
                    "lts_versions": [16, 18, 20, 22],
                    "step_by": 2,
                    "skip_versions": ["19", "21", "23"]
                },
                "debian": {
                    "level": 1
                }
            }
            """)
        
        result = load_custom_rules(rules_file)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["node"]["level"], 1)
        self.assertEqual(result["node"]["lts_versions"], [16, 18, 20, 22])
        self.assertEqual(result["node"]["step_by"], 2)
        self.assertEqual(result["node"]["skip_versions"], ["19", "21", "23"])
        self.assertEqual(result["debian"]["level"], 1)
        
        # Invalid JSON file
        invalid_file = os.path.join(self.test_dir, "invalid.json")
        with open(invalid_file, "w") as f:
            f.write("This is not valid JSON")
        
        result = load_custom_rules(invalid_file)
        self.assertEqual(result, {})
        
        # Non-existent file
        result = load_custom_rules("/path/to/nonexistent/rules.json")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()