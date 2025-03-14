import unittest
import os
import tempfile
from dockerfile_parser import extract_base_images

class TestDockerfileParser(unittest.TestCase):
    
    def setUp(self):
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up temporary files
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)
    
    def create_dockerfile(self, content):
        """Helper to create a test Dockerfile with specified content"""
        file_path = os.path.join(self.test_dir, "Dockerfile")
        with open(file_path, "w") as f:
            f.write(content)
        return file_path
    
    def test_extract_single_image(self):
        """Test extracting a single image from a Dockerfile"""
        dockerfile_content = """
        FROM python:3.9-alpine
        
        WORKDIR /app
        COPY . .
        RUN pip install -r requirements.txt
        CMD ["python", "app.py"]
        """
        
        dockerfile_path = self.create_dockerfile(dockerfile_content)
        result = extract_base_images(dockerfile_path)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["image"], "python:3.9-alpine")
        self.assertIsNone(result[0]["stage"])
    
    def test_extract_multiple_images(self):
        """Test extracting multiple images from a multi-stage Dockerfile"""
        dockerfile_content = """
        FROM golang:1.19 AS builder
        
        WORKDIR /app
        COPY . .
        RUN go build -o main .
        
        FROM alpine:3.17
        COPY --from=builder /app/main /app/main
        CMD ["/app/main"]
        """
        
        dockerfile_path = self.create_dockerfile(dockerfile_content)
        result = extract_base_images(dockerfile_path)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["image"], "golang:1.19")
        self.assertEqual(result[1]["image"], "alpine:3.17")
        self.assertIsNone(result[1]["stage"])
    
    def test_extract_with_platform(self):
        """Test extracting an image with platform specification"""
        dockerfile_content = """
        FROM --platform=linux/amd64 node:16
        
        WORKDIR /app
        COPY . .
        RUN npm install
        CMD ["npm", "start"]
        """
        
        dockerfile_path = self.create_dockerfile(dockerfile_content)
        result = extract_base_images(dockerfile_path)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["image"], "node:16")
        self.assertIsNone(result[0]["stage"])
    
    def test_extract_no_image(self):
        """Test behavior with a Dockerfile that doesn't contain FROM"""
        dockerfile_content = """
        # This is an invalid Dockerfile with no FROM instruction
        WORKDIR /app
        COPY . .
        RUN echo "Hello World"
        """
        
        dockerfile_path = self.create_dockerfile(dockerfile_content)
        result = extract_base_images(dockerfile_path)
        
        self.assertEqual(result, [])
    
    def test_invalid_dockerfile_path(self):
        """Test behavior with a non-existent Dockerfile"""
        result = extract_base_images("/path/to/nonexistent/Dockerfile")
        self.assertEqual(result, [])

if __name__ == "__main__":
    unittest.main()