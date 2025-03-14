import os
import re
import fnmatch

class ImageIgnoreManager:
    """
    Manager for handling image ignore patterns and rules.
    Used to determine if a specific Docker image should be ignored during analysis.
    """
    
    def __init__(self):
        """Initialize the ignore manager with empty patterns."""
        self.patterns = []
    
    def add_pattern(self, pattern):
        """
        Add a single ignore pattern.
        
        Args:
            pattern: A glob pattern (e.g., "python:*", "node:14*") to match against image names
            
        Returns:
            None
        """
        if pattern and pattern.strip():
            self.patterns.append(pattern.strip())
    
    def add_patterns_from_list(self, patterns):
        """
        Add multiple ignore patterns from a list.
        
        Args:
            patterns: List of glob patterns
            
        Returns:
            None
        """
        if patterns:
            for pattern in patterns:
                self.add_pattern(pattern)
    
    def load_patterns_from_file(self, file_path):
        """
        Load ignore patterns from a file.
        Each line in the file should contain one pattern.
        Empty lines and lines starting with # are ignored.
        
        Args:
            file_path: Path to the file containing ignore patterns
            
        Returns:
            bool: True if file was loaded successfully, False otherwise
        """
        if not os.path.isfile(file_path):
            print(f"Warning: Ignore file '{file_path}' not found.")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Skip comments and empty lines
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    self.add_pattern(line)
            return True
        except Exception as e:
            print(f"Error reading ignore file: {str(e)}")
            return False
    
    def should_ignore(self, image_name):
        """
        Check if an image should be ignored based on the patterns.
        
        Args:
            image_name: The image name to check against ignore patterns
            
        Returns:
            bool: True if the image should be ignored, False otherwise
        """
        if not self.patterns:
            return False
            
        for pattern in self.patterns:
            # Check if pattern starts with regex: to use regex matching
            if pattern.startswith('regex:'):
                regex_pattern = pattern[6:]  # Remove the 'regex:' prefix
                try:
                    if re.search(regex_pattern, image_name):
                        return True
                except re.error:
                    print(f"Warning: Invalid regex pattern: {regex_pattern}")
            else:
                # Use glob pattern matching
                if fnmatch.fnmatch(image_name, pattern):
                    return True
        
        return False
    
    def get_patterns(self):
        """Get the list of current ignore patterns."""
        return self.patterns.copy()


def parse_ignore_options(args):
    """
    Parse command line arguments for image ignore options.
    
    Args:
        args: Command line arguments
        
    Returns:
        ImageIgnoreManager instance configured with the specified patterns
    """
    ignore_manager = ImageIgnoreManager()
    
    # Check for ignore patterns
    ignore_patterns = []
    i = 0
    while i < len(args):
        if args[i] == '--ignore':
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                ignore_patterns.append(args[i + 1])
                i += 2
            else:
                print("Warning: --ignore flag used without a pattern.")
                i += 1
        else:
            i += 1
    
    # Add patterns from command line
    ignore_manager.add_patterns_from_list(ignore_patterns)
    
    # Check for ignore file
    if '--ignore-images' in args:
        try:
            idx = args.index('--ignore-images')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                file_path = args[idx + 1]
                success = ignore_manager.load_patterns_from_file(file_path)
                if success:
                    print(f"Loaded ignore patterns from: {file_path}")
            else:
                print("Warning: --ignore-images flag used without a file path.")
        except ValueError:
            pass
    
    # Print ignore patterns if any were specified
    patterns = ignore_manager.get_patterns()
    if patterns:
        print("Using image ignore patterns:")
        for pattern in patterns:
            print(f"  - {pattern}")
    
    return ignore_manager