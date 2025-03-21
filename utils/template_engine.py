import os
import json
import jinja2
import pkg_resources
from typing import Dict, Any, List, Optional

class TemplateEngine:
    """Class for rendering HTML templates using Jinja2."""
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the template engine.
        
        Args:
            templates_dir: Directory containing templates. If None, uses the default directory.
        """
        # Try to find the templates directory
        if templates_dir is None:
            # Check in development environment (next to current file)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            templates_dir = os.path.join(os.path.dirname(current_dir), 'templates')
            
            # If not found, check in installed package
            if not os.path.exists(templates_dir):
                try:
                    templates_dir = pkg_resources.resource_filename('docker_analyzer', 'templates')
                except (ImportError, pkg_resources.DistributionNotFound):
                    # Fallback to creating a templates directory if needed
                    os.makedirs(templates_dir, exist_ok=True)
        
        # Create Jinja2 environment
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(templates_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Register custom filters
        self.env.filters['default'] = self._default_filter
        
        # Store templates directory
        self.templates_dir = templates_dir
    
    def _default_filter(self, value, default_value='N/A'):
        """Custom filter to provide default value if None."""
        return default_value if value is None else value
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.
        
        Args:
            template_name: Name of the template file
            context: Dictionary of variables to pass to the template
            
        Returns:
            Rendered template as string
        """
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    def render_string_template(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Render a template string with the given context.
        
        Args:
            template_string: Template string to render
            context: Dictionary of variables to pass to the template
            
        Returns:
            Rendered template as string
        """
        template = self.env.from_string(template_string)
        return template.render(**context)
    
    def ensure_template_file(self, template_name: str, template_content: str) -> None:
        """
        Ensure that a template file exists, create it if it doesn't.
        
        Args:
            template_name: Name of the template file
            template_content: Content to write if the file doesn't exist
        """
        template_path = os.path.join(self.templates_dir, template_name)
        
        # Check if file exists
        if not os.path.exists(template_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(template_path), exist_ok=True)
            
            # Write template content
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            print(f"Created template file: {template_path}")