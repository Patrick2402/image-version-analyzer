import sys
import os
from formatters import get_formatter

def add_output_options_to_help():
    """Return help text for output options"""
    return """
Output Options:
  --output FORMAT: Specify output format (text, json, html, csv, markdown)
  --report-file PATH: Save analysis results to specified file
  --no-timestamp: Do not include timestamp in the report
"""

def parse_output_options(args):
    """
    Parse output-related command line arguments.
    
    Args:
        args: Command line arguments
        
    Returns:
        Dictionary containing output options
    """
    options = {
        'output_format': 'text',  # Default format
        'report_file': None,
        'include_timestamp': True,
    }
    
    # Check for output format
    if '--output' in args:
        try:
            idx = args.index('--output')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                options['output_format'] = args[idx + 1]
        except (ValueError, IndexError):
            pass
    
    # Check for report file
    if '--report-file' in args:
        try:
            idx = args.index('--report-file')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                options['report_file'] = args[idx + 1]
        except (ValueError, IndexError):
            pass
    
    # Check for timestamp flag
    if '--no-timestamp' in args:
        options['include_timestamp'] = False
    
    return options

def format_and_save_results(results, total_images, options):
    """
    Format results and optionally save to file.
    
    Args:
        results: List of image analysis results
        total_images: Total number of images analyzed
        options: Output options
        
    Returns:
        Formatted output as string
    """
    # Get the appropriate formatter
    formatter = get_formatter(
        options['output_format'], 
        include_timestamp=options['include_timestamp']
    )
    
    # Format the results
    output = formatter.format(results, total_images)
    
    # Save to file if specified
    if options['report_file']:
        success = formatter.save_to_file(output, options['report_file'])
        if success:
            print(f"Report saved to: {options['report_file']}")
        else:
            print(f"Failed to save report to: {options['report_file']}")
    
    return output

def integrate_with_main(original_main):
    """
    Integrate the output formatting with the main function.
    
    Args:
        original_main: Original main function to wrap
        
    Returns:
        New main function with output formatting
    """
    def new_main():
        # Add output options to help text
        if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
            original_main()  # Show original help
            print(add_output_options_to_help())
            return
        
        # Parse output options
        output_options = parse_output_options(sys.argv)
        
        # Run the original analysis logic
        # This is a placeholder - we need to modify the original main 
        # to return results instead of printing directly
        results = []
        total_images = 0
        
        # Format and save results
        formatted_output = format_and_save_results(results, total_images, output_options)
        
        # Print to console unless it's being saved to a file and not text format
        if not output_options['report_file'] or output_options['output_format'] == 'text':
            print(formatted_output)
    
    return new_main

# Example of how to integrate with actual main function
"""
from original_module import main as original_main

# Replace the original main with the wrapped version
main = integrate_with_main(original_main)

if __name__ == "__main__":
    main()
"""