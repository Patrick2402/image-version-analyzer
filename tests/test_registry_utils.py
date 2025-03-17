import unittest
from unittest.mock import patch, MagicMock
from registry_utils import (
    is_supported_registry,
    get_public_image_name,
    is_valid_version_tag,
    find_recommended_tag
)

class TestRegistryUtils(unittest.TestCase):
    
    def test_is_supported_registry(self):
        """Test identification of supported/unsupported registries"""
        # Docker Hub image (supported)
        is_supported, registry = is_supported_registry("python:3.9")
        self.assertTrue(is_supported)
        self.assertIsNone(registry)
        
        # Docker Hub with organization (supported)
        is_supported, registry = is_supported_registry("bitnami/postgresql:14")
        self.assertTrue(is_supported)
        self.assertIsNone(registry)
        
        # Google Container Registry (unsupported)
        is_supported, registry = is_supported_registry("gcr.io/project/image:tag")
        self.assertFalse(is_supported)
        self.assertEqual(registry, "gcr.io")
        
        # GitHub Container Registry (unsupported)
        is_supported, registry = is_supported_registry("ghcr.io/user/image:tag")
        self.assertFalse(is_supported)
        self.assertEqual(registry, "ghcr.io")
        
        # Quay.io (unsupported)
        is_supported, registry = is_supported_registry("quay.io/user/image:tag")
        self.assertFalse(is_supported)
        self.assertEqual(registry, "quay.io")
    
    def test_get_public_image_name(self):
        """Test extraction of public image name from private registry image"""
        # No private registry
        self.assertEqual(
            get_public_image_name("python:3.9", []),
            "python:3.9"
        )
        
        # With private registry
        self.assertEqual(
            get_public_image_name("registry.example.com/python:3.9", ["registry.example.com"]),
            "python:3.9"
        )
        
        # With private registry and path
        self.assertEqual(
            get_public_image_name("registry.example.com/library/python:3.9", ["registry.example.com"]),
            "library/python:3.9"
        )
        
        # With private registry not in the list
        self.assertEqual(
            get_public_image_name("other-registry.com/python:3.9", ["registry.example.com"]),
            "other-registry.com/python:3.9"
        )
    
    def test_is_valid_version_tag(self):
        """Test validation of version tags"""
        # Valid version tags
        self.assertTrue(is_valid_version_tag("1.0.0"))
        self.assertTrue(is_valid_version_tag("v2.1.0"))
        self.assertTrue(is_valid_version_tag("3.19"))
        self.assertTrue(is_valid_version_tag("1.24-alpine"))
        
        # Invalid version tags (dates, etc.)
        self.assertFalse(is_valid_version_tag("20220101"))
        self.assertFalse(is_valid_version_tag("latest"))
        self.assertFalse(is_valid_version_tag("alpine"))
        self.assertFalse(is_valid_version_tag("1.2.3.4.5.6"))
        self.assertFalse(is_valid_version_tag("1.2.3-alpha.beta.gamma"))
    
    def test_find_recommended_tag(self):
        """Test finding the newest semantic version from available tags"""
        # Simple numeric versions
        tags = ["1.0.0", "1.1.0", "1.2.0", "2.0.0"]
        self.assertEqual(find_recommended_tag(tags), "2.0.0")
        
        # With 'v' prefix
        tags = ["v1.0.0", "v1.1.0", "v1.2.0", "v2.0.0"]
        self.assertEqual(find_recommended_tag(tags), "v2.0.0")
        
        # With variants
        tags = ["1.0.0-alpine", "1.1.0-alpine", "1.2.0-alpine", "2.0.0-alpine"]
        self.assertEqual(find_recommended_tag(tags), "2.0.0-alpine")
        
        # Mixed prefixes and variants
        tags = ["1.0.0", "v1.1.0", "1.2.0-alpine", "v2.0.0-slim"]
        self.assertEqual(find_recommended_tag(tags), "v2.0.0-slim")
        
        # With development versions that should be filtered out
        tags = ["1.0.0", "1.1.0", "2.0.0-beta", "2.0.0-rc1", "1.2.0"]
        self.assertEqual(find_recommended_tag(tags), "1.2.0")
        
        # Empty tags
        self.assertIsNone(find_recommended_tag([]))


if __name__ == "__main__":
    unittest.main()