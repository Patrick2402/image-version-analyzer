import json
import csv
import os
import io
from datetime import datetime
import jinja2

class BaseFormatter:
    """Base class for all formatters"""
    
    def __init__(self, include_timestamp=True):
        self.include_timestamp = include_timestamp
    
    def format(self, results, total_images, original_count=None, github_info=None):
        """
        Format the results.
        
        Args:
            results: List of image analysis results
            total_images: Total number of images analyzed (after filtering)
            original_count: Original number of images before filtering (optional)
            github_info: Information about GitHub repository (optional)
            
        Returns:
            String representation of formatted results
        """
        raise NotImplementedError("Subclasses must implement format method")
    
    def save_to_file(self, content, filename):
        """
        Save formatted content to a file.
        
        Args:
            content: Formatted content as string
            filename: Path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving to file: {str(e)}")
            return False
    
    def get_timestamp(self):
        """Get current timestamp formatted as string"""
        if self.include_timestamp:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return None
    
    def get_summary(self, results):
        """Get summary stats of results"""
        # Filter out the special IGNORED_IMAGES_SUMMARY entry if it exists
        filtered_results = [r for r in results if r.get('status') != 'INFO']
        
        outdated = [r for r in filtered_results if r['status'] == 'OUTDATED']
        warnings = [r for r in filtered_results if r['status'] == 'WARNING']
        unknown = [r for r in filtered_results if r['status'] == 'UNKNOWN']
        up_to_date = [r for r in filtered_results if r['status'] == 'UP-TO-DATE']
        
        # Find ignored images info if present
        ignored_info = next((r for r in results if r.get('image') == 'IGNORED_IMAGES_SUMMARY'), None)
        
        return {
            'total': len(filtered_results),
            'outdated': len(outdated),
            'warnings': len(warnings),
            'unknown': len(unknown),
            'up_to_date': len(up_to_date),
            'outdated_images': outdated,
            'warning_images': warnings,
            'unknown_images': unknown,
            'up_to_date_images': up_to_date,
            'ignored_info': ignored_info
        }


class TextFormatter(BaseFormatter):
    """Format results as plain text with ultra simple formatting"""
    
    def format(self, results, total_images, original_count=None, github_info=None):
        output = []
        
        # Add timestamp
        timestamp = self.get_timestamp()
        if timestamp:
            output.append(f"Analysis Time: {timestamp}")
        
        # Header
        if original_count and original_count > total_images:
            output.append(f"Found {original_count} images in Dockerfile, {original_count - total_images} ignored")
        else:
            output.append(f"Found {total_images} image(s) in Dockerfile:")
            for i, result in enumerate([r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY'], 1):
                output.append(f"{i}. {result['image']}")
        
        # Get summary stats
        summary = self.get_summary(results)
        
        # Analysis summary
        output.append("\n==================================================")
        output.append("ANALYSIS SUMMARY")
        output.append("==================================================")
        
        # Add outdated images summary
        if summary['outdated'] > 0:
            output.append(f"\n⛔ {summary['outdated']} OUTDATED IMAGE(S):")
            for img in summary['outdated_images']:
                output.append(f"  - {img['image']} : {img['message']}")
        
        # Add warning images summary
        if summary['warnings'] > 0:
            output.append(f"\n⚠️ {summary['warnings']} WARNING(S):")
            for img in summary['warning_images']:
                output.append(f"  - {img['image']} : {img['message']}")
        
        # Add unknown images summary
        if summary['unknown'] > 0:
            output.append(f"\n❓ {summary['unknown']} UNKNOWN STATUS:")
            for img in summary['unknown_images']:
                output.append(f"  - {img['image']} : {img['message']}")
        
        # Final status summary
        if not summary['outdated'] and not summary['warnings'] and not summary['unknown']:
            output.append("\n✅ ALL IMAGES UP-TO-DATE")
        elif summary['outdated'] > 0:
            output.append("\n⛔ RESULT: OUTDATED - At least one image is outdated beyond threshold")
        else:
            output.append("\n⚠️ RESULT: WARNING - Some images have warnings or unknown status")
        
        return "\n".join(output)


class JsonFormatter(BaseFormatter):
    """Format results as JSON"""
    
    def format(self, results, total_images, original_count=None, github_info=None):
        # Create a copy of results excluding the special entries
        filtered_results = [r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY']
        
        # Find ignored images info if present
        ignored_info = next((r for r in results if r.get('image') == 'IGNORED_IMAGES_SUMMARY'), None)
        ignored_images = ignored_info.get('ignored_images', []) if ignored_info else []
        
        output = {
            'total_images': total_images,
            'results': filtered_results,
            'summary': self.get_summary(results),
        }
        
        # Add GitHub info if available
        if github_info:
            output['github'] = github_info
        
        # Add original count and ignored images if applicable
        if original_count and original_count > total_images:
            output['original_count'] = original_count
            output['ignored_count'] = original_count - total_images
            output['ignored_images'] = ignored_images
        
        timestamp = self.get_timestamp()
        if timestamp:
            output['timestamp'] = timestamp
        
        json_output = json.dumps(output, indent=2)
        return self.add_security_to_json(json_output, results)
    
    def add_security_to_json(self, output, results):
        """Add security information to JSON output"""
        # Check if we have security information
        has_security_info = any('security' in result for result in results)
        if not has_security_info:
            return output
        
        # Count security statuses
        vulnerable_count = sum(1 for r in results if 'security' in r and r['security']['status'] == 'VULNERABLE')
        secure_count = sum(1 for r in results if 'security' in r and r['security']['status'] == 'SECURE')
        error_count = sum(1 for r in results if 'security' in r and r['security']['status'] == 'ERROR')
        
        # Add security section to the output
        output_dict = json.loads(output)
        output_dict['security'] = {
            'scanned': vulnerable_count + secure_count + error_count,
            'vulnerable': vulnerable_count,
            'secure': secure_count,
            'errors': error_count,
            'status': 'VULNERABLE' if vulnerable_count > 0 else 'WARNING' if error_count > 0 else 'SECURE'
        }
        
        # Update the results with security information
        for i, result in enumerate(output_dict['results']):
            image_name = result.get('image')
            if not image_name:
                continue
            
            # Find the security info for this image
            for original_result in results:
                if original_result.get('image') == image_name and 'security' in original_result:
                    output_dict['results'][i]['security'] = original_result['security']
                    break
        
        return json.dumps(output_dict, indent=2)


class CsvFormatter(BaseFormatter):
    """Format results as CSV"""
    
    def format(self, results, total_images, original_count=None, github_info=None):
        output = io.StringIO()
        
        # Determine if we need to include a repository column
        has_repo_info = any('repository' in result for result in results)
        include_repo = has_repo_info or (github_info and 'repo' in github_info)
        
        if include_repo:
            fieldnames = ['image', 'repository', 'status', 'current', 'recommended', 'gap', 'message']
        else:
            fieldnames = ['image', 'status', 'current', 'recommended', 'gap', 'message']
        
        # Add GitHub info as comments if available
        if github_info:
            output.write(f"# GitHub Repository: {github_info.get('org_or_user')}/{github_info.get('repo')}\n")
            output.write(f"# Dockerfile Path: {github_info.get('path')}\n")
            output.write(f"# GitHub URL: {github_info.get('url')}\n\n")
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        # Filter out special entries
        filtered_results = [r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY']
        
        for result in filtered_results:
            # Create a new row with only the fields we want
            row = {field: result.get(field, '') for field in fieldnames if field != 'repository'}
            
            # Add repository if needed
            if include_repo:
                if 'repository' in result:
                    row['repository'] = result['repository']
                elif github_info and 'repo' in github_info:
                    row['repository'] = github_info['repo']
                else:
                    row['repository'] = 'N/A'
                
            writer.writerow(row)
        
        # Add ignored images as metadata
        ignored_info = next((r for r in results if r.get('image') == 'IGNORED_IMAGES_SUMMARY'), None)
        if ignored_info and 'ignored_images' in ignored_info:
            output.write("\n# Ignored Images\n")
            for img in ignored_info['ignored_images']:
                output.write(f"# {img}\n")
        
        return output.getvalue()


class MarkdownFormatter(BaseFormatter):
    """Format results as Markdown"""
    
    def format(self, results, total_images, original_count=None, github_info=None):
        output = []
        
        # Add title and timestamp
        output.append("# Docker Image Analysis Report")
        
        timestamp = self.get_timestamp()
        if timestamp:
            output.append(f"*Generated on: {timestamp}*\n")
        
        # Add GitHub info if available
        if github_info:
            output.append("## Repository Information")
            output.append(f"- **GitHub Repository:** {github_info.get('org_or_user')}/{github_info.get('repo')}")
            output.append(f"- **Dockerfile Path:** {github_info.get('path')}")
            output.append(f"- **GitHub URL:** [{github_info.get('path')}]({github_info.get('url')})\n")
        
        # Find ignored images info if present
        ignored_info = next((r for r in results if r.get('image') == 'IGNORED_IMAGES_SUMMARY'), None)
        ignored_images = ignored_info.get('ignored_images', []) if ignored_info else []
        
        # Images found section with ignored count if applicable
        if original_count and original_count > total_images:
            ignored_count = original_count - total_images
            output.append(f"## Found {original_count} image(s), {ignored_count} ignored")
        else:
            output.append(f"## Found {total_images} image(s)")
        
        # Get filtered results (exclude special entries)
        filtered_results = [r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY']
        
        output.append("| # | Image |")
        output.append("| --- | --- |")
        for i, result in enumerate(filtered_results, 1):
            output.append(f"| {i} | `{result['image']}` |")
        
        # Add ignored images section if applicable
        if ignored_images:
            output.append("\n## Ignored Images")
            output.append("| # | Image |")
            output.append("| --- | --- |")
            for i, img in enumerate(ignored_images, 1):
                output.append(f"| {i} | `{img}` |")
        
        # Summary
        output.append("\n## Analysis Summary")
        
        summary = self.get_summary(results)
        
        # Results table - with or without Repository column
        output.append("\n### Detailed Results")
        
        # Check if we have repository info in results or in github_info
        has_repo_info = any('repository' in result for result in filtered_results)
        
        if has_repo_info:
            output.append("| Image | Repository | Status | Current | Recommended | Gap | Message |")
            output.append("| --- | --- | --- | --- | --- | --- | --- |")
            
            for result in filtered_results:
                status_emoji = "✅" if result['status'] == 'UP-TO-DATE' else "⛔" if result['status'] == 'OUTDATED' else "⚠️" if result['status'] == 'WARNING' else "❓"
                
                current = result.get('current', 'N/A')
                recommended = result.get('recommended', 'N/A')
                gap = str(result.get('gap', 'N/A'))
                repository = result.get('repository', 'N/A')
                
                output.append(f"| `{result['image']}` | {repository} | {status_emoji} {result['status']} | {current} | {recommended} | {gap} | {result['message']} |")
        elif github_info and 'repo' in github_info:
            output.append("| Image | Repository | Status | Current | Recommended | Gap | Message |")
            output.append("| --- | --- | --- | --- | --- | --- | --- |")
            
            for result in filtered_results:
                status_emoji = "✅" if result['status'] == 'UP-TO-DATE' else "⛔" if result['status'] == 'OUTDATED' else "⚠️" if result['status'] == 'WARNING' else "❓"
                
                current = result.get('current', 'N/A')
                recommended = result.get('recommended', 'N/A')
                gap = str(result.get('gap', 'N/A'))
                
                output.append(f"| `{result['image']}` | {github_info['repo']} | {status_emoji} {result['status']} | {current} | {recommended} | {gap} | {result['message']} |")
        else:
            output.append("| Image | Status | Current | Recommended | Gap | Message |")
            output.append("| --- | --- | --- | --- | --- | --- |")
            
            for result in filtered_results:
                status_emoji = "✅" if result['status'] == 'UP-TO-DATE' else "⛔" if result['status'] == 'OUTDATED' else "⚠️" if result['status'] == 'WARNING' else "❓"
                
                current = result.get('current', 'N/A')
                recommended = result.get('recommended', 'N/A')
                gap = str(result.get('gap', 'N/A'))
                
                output.append(f"| `{result['image']}` | {status_emoji} {result['status']} | {current} | {recommended} | {gap} | {result['message']} |")
        
        # Conclusion
        output.append("\n## Conclusion")
        
        if not summary['outdated'] and not summary['warnings'] and not summary['unknown']:
            output.append("✅ **ALL IMAGES UP-TO-DATE**")
        elif summary['outdated']:
            output.append("⛔ **RESULT: OUTDATED** - At least one image is outdated beyond threshold")
            
            # Add list of outdated images
            output.append("\n### Outdated Images")
            for img in summary['outdated_images']:
                current = img.get('current', 'N/A')
                recommended = img.get('recommended', 'N/A')
                repository = img.get('repository', '')
                repo_info = f" ({repository})" if repository else ""
                output.append(f"- `{img['image']}`{repo_info}: {current} → {recommended} ({img['message']})")
        else:
            output.append("⚠️ **RESULT: WARNING** - Some images have warnings or unknown status")
        
        # Add security section if available
        security_section = self.add_security_section_markdown(results)
        if security_section:
            output.append(security_section)
        
        return "\n".join(output)
    
    def add_security_section_markdown(self, results):
        """Format security information as Markdown"""
        security_output = []
        
        # Check if we have security information
        has_security_info = any('security' in result for result in results)
        if not has_security_info:
            return ""
        
        security_output.append("\n## Security Scan Results")
        
        # Count security statuses
        vulnerable_images = []
        secure_images = []
        error_images = []
        
        for result in results:
            if 'security' in result and result['security']['status'] == 'VULNERABLE':
                vulnerable_images.append(result)
            elif 'security' in result and result['security']['status'] == 'SECURE':
                secure_images.append(result)
            elif 'security' in result and result['security']['status'] == 'ERROR':
                error_images.append(result)
        
        security_output.append(f"\nImages scanned for vulnerabilities: **{len(vulnerable_images) + len(secure_images) + len(error_images)}**")
        
        if vulnerable_images:
            security_output.append(f"\n### ⛔ {len(vulnerable_images)} Vulnerable Image(s)")
            security_output.append("\n| Image | Vulnerabilities | Critical | High | Medium | Low | Fixable |")
            security_output.append("| --- | --- | --- | --- | --- | --- | --- |")
            
            for img in vulnerable_images:
                summary = img['security']['summary']
                severities = summary['severities']
                security_output.append(f"| `{img['image']}` | {summary['total']} | {severities['critical']} | " +
                           f"{severities['high']} | {severities['medium']} | {severities['low']} | {summary['fixable']} |")
        
        if secure_images:
            security_output.append(f"\n### ✅ {len(secure_images)} Secure Image(s)")
            security_output.append("\n| Image | Status |")
            security_output.append("| --- | --- |")
            
            for img in secure_images:
                security_output.append(f"| `{img['image']}` | No vulnerabilities found |")
        
        if error_images:
            security_output.append(f"\n### ❓ {len(error_images)} Error(s) During Scan")
            security_output.append("\n| Image | Error |")
            security_output.append("| --- | --- |")
            
            for img in error_images:
                security_output.append(f"| `{img['image']}` | {img['security']['message']} |")
        
        if vulnerable_images:
            security_output.append("\n### Security Conclusion")
            security_output.append("\n⛔ **RESULT: VULNERABLE** - Vulnerabilities found in one or more images")
        elif error_images:
            security_output.append("\n### Security Conclusion")
            security_output.append("\n⚠️ **RESULT: WARNING** - Errors during security scan")
        else:
            security_output.append("\n### Security Conclusion")
            security_output.append("\n✅ **RESULT: SECURE** - No vulnerabilities found")
        
        return "\n".join(security_output)


class HtmlFormatter(BaseFormatter):
    """Format results as HTML with a modern dark template."""
    
    TEMPLATE_FILE = 'dark_template.html'
    
    def __init__(self, include_timestamp=True, theme='dark'):
        """
        Initialize the HTML formatter.
        
        Args:
            include_timestamp: Whether to include timestamp in the output
            theme: Theme to use ('dark' or 'light')
        """
        super().__init__(include_timestamp)
        self.theme = theme
        
        # Try to import Jinja2, install if not available
        try:
            import jinja2
        except ImportError:
            print("Jinja2 not found. Installing...")
            import subprocess
            subprocess.check_call(["pip", "install", "jinja2"])
            import jinja2
        
        # Ensure template directory exists
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.templates_dir = os.path.join(os.path.dirname(current_dir), 'templates')
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Register custom filters
        self.jinja_env.filters['default'] = lambda value, default='N/A': default if value is None else value
        
        # Ensure template file exists
        self._ensure_template_file()
    
    def _ensure_template_file(self):
        """Ensure that the template file exists, create it if it doesn't."""
        template_path = os.path.join(self.templates_dir, self.TEMPLATE_FILE)
        
        # Create template file if it doesn't exist
        if not os.path.exists(template_path):
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(self._get_default_template())
    
    def _get_default_template(self):
        """Get the default template content."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Image Analysis Report</title>
    <style>
        :root {
            --bg-primary: #121212;
            --bg-secondary: #1e1e1e;
            --bg-tertiary: #2d2d2d;
            --text-primary: #ffffff;
            --text-secondary: #b3b3b3;
            --accent-blue: #4da6ff;
            --accent-green: #4ecca3;
            --accent-red: #ff6b6b;
            --accent-yellow: #ffe66d;
            --accent-purple: #a16ae8;
            
            --success: #2ecc71;
            --danger: #e74c3c;
            --warning: #f39c12;
            --info: #3498db;
            --unknown: #7f8c8d;
            
            --border-radius: 8px;
            --card-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background-color: var(--bg-primary);
            padding: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        h1, h2, h3 {
            color: var(--accent-blue);
            margin-bottom: 16px;
        }
        
        h1 {
            font-size: 28px;
            border-bottom: 2px solid var(--accent-blue);
            padding-bottom: 10px;
            margin-bottom: 24px;
        }
        
        h2 {
            font-size: 22px;
            margin-top: 30px;
        }
        
        h3 {
            font-size: 18px;
            color: var(--text-primary);
        }
        
        p {
            margin-bottom: 16px;
            color: var(--text-secondary);
        }
        
        a {
            color: var(--accent-blue);
            text-decoration: none;
            transition: color 0.2s;
        }
        
        a:hover {
            color: var(--accent-purple);
            text-decoration: underline;
        }
        
        .card {
            background-color: var(--bg-secondary);
            border-radius: var(--border-radius);
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: var(--card-shadow);
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        
        .metric-card {
            background-color: var(--bg-tertiary);
            border-radius: var(--border-radius);
            padding: 20px;
            box-shadow: var(--card-shadow);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        
        .metric-title {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }
        
        .metric-value {
            font-size: 32px;
            font-weight: bold;
        }
        
        .metric-up-to-date .metric-value {
            color: var(--success);
        }
        
        .metric-outdated .metric-value {
            color: var(--danger);
        }
        
        .metric-warning .metric-value {
            color: var(--warning);
            .metric-warning .metric-value {
            color: var(--warning);
        }
        
        .metric-unknown .metric-value {
            color: var(--unknown);
        }
        
        .result-status {
            font-size: 18px;
            font-weight: bold;
            padding: 12px 16px;
            border-radius: var(--border-radius);
            text-align: center;
            margin-bottom: 24px;
        }
        
        .result-status.success {
            background-color: rgba(46, 204, 113, 0.2);
            border: 1px solid var(--success);
            color: var(--success);
        }
        
        .result-status.danger {
            background-color: rgba(231, 76, 60, 0.2);
            border: 1px solid var(--danger);
            color: var(--danger);
        }
        
        .result-status.warning {
            background-color: rgba(243, 156, 18, 0.2);
            border: 1px solid var(--warning);
            color: var(--warning);
        }
        
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-bottom: 24px;
            border-radius: var(--border-radius);
            overflow: hidden;
        }
        
        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--bg-tertiary);
        }
        
        th {
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            font-weight: 600;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        tr:hover td {
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        code {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: var(--bg-tertiary);
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 0.9em;
            color: var(--accent-green);
        }
        
        pre {
            background-color: var(--bg-tertiary);
            padding: 16px;
            border-radius: var(--border-radius);
            overflow-x: auto;
            margin-bottom: 24px;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
            margin-right: 6px;
        }
        
        .badge-success {
            background-color: var(--success);
            color: #ffffff;
        }
        
        .badge-danger {
            background-color: var(--danger);
            color: #ffffff;
        }
        
        .badge-warning {
            background-color: var(--warning);
            color: #ffffff;
        }
        
        .badge-unknown {
            background-color: var(--unknown);
            color: #ffffff;
        }
        
        .badge-info {
            background-color: var(--info);
            color: #ffffff;
        }
        
        .repo-info {
            background-color: var(--bg-tertiary);
            padding: 16px;
            border-radius: var(--border-radius);
            margin-bottom: 24px;
            border-left: 4px solid var(--accent-blue);
        }
        
        .repo-info p {
            margin-bottom: 8px;
        }
        
        .repo-info p:last-child {
            margin-bottom: 0;
        }
        
        .flex-container {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 24px;
        }
        
        .flex-item {
            flex: 1;
            min-width: 300px;
        }
        
        .timestamp {
            font-style: italic;
            color: var(--text-secondary);
            margin-bottom: 24px;
        }
        
        .status-cell.success {
            color: var(--success);
        }
        
        .status-cell.danger {
            color: var(--danger);
        }
        
        .status-cell.warning {
            color: var(--warning);
        }
        
        .status-cell.unknown {
            color: var(--unknown);
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            body {
                padding: 15px;
            }
            
            .summary-grid {
                grid-template-columns: 1fr;
            }
            
            table {
                display: block;
                overflow-x: auto;
            }
        }
    </style>
</head>
<body>
    <h1>Docker Image Analysis Report</h1>
    
    <!-- Timestamp -->
    {% if timestamp %}
    <p class="timestamp">Generated on: {{ timestamp }}</p>
    {% endif %}
    
    <!-- Repository Info -->
    {% if github_info %}
    <div class="repo-info">
        {% if github_info.org_or_user and github_info.repo %}
        <p><strong>GitHub Repository:</strong> {{ github_info.org_or_user }}/{{ github_info.repo }}</p>
        {% elif github_info.org_or_user %}
        <p><strong>GitHub Organization/User:</strong> {{ github_info.org_or_user }}</p>
        {% endif %}
        
        {% if github_info.path %}
        <p><strong>Dockerfile Path:</strong> {{ github_info.path }}</p>
        {% endif %}
        
        {% if github_info.url %}
        <p><a href="{{ github_info.url }}" target="_blank">View on GitHub</a></p>
        {% endif %}
    </div>
    {% endif %}
    
    <!-- Summary Cards -->
    <div class="card">
        <h2>Summary</h2>
        
        {% if original_count and original_count > total_images %}
        <p>Found <strong>{{ original_count }}</strong> image(s) in Dockerfile, <span class="badge badge-info">{{ original_count - total_images }}</span> images ignored</p>
        {% else %}
        <p>Found <strong>{{ total_images }}</strong> image(s) in Dockerfile</p>
        {% endif %}
        
        <div class="summary-grid">
            <div class="metric-card metric-up-to-date">
                <div class="metric-title">Up-to-date</div>
                <div class="metric-value">{{ summary.up_to_date }}</div>
            </div>
            
            <div class="metric-card metric-outdated">
                <div class="metric-title">Outdated</div>
                <div class="metric-value">{{ summary.outdated }}</div>
            </div>
            
            <div class="metric-card metric-warning">
                <div class="metric-title">Warnings</div>
                <div class="metric-value">{{ summary.warnings }}</div>
            </div>
            
            <div class="metric-card metric-unknown">
                <div class="metric-title">Unknown</div>
                <div class="metric-value">{{ summary.unknown }}</div>
            </div>
        </div>
        
        <!-- Result Status -->
        {% if not summary.outdated and not summary.warnings and not summary.unknown %}
        <div class="result-status success">✅ ALL IMAGES UP-TO-DATE</div>
        {% elif summary.outdated %}
        <div class="result-status danger">⛔ OUTDATED - At least one image is outdated beyond threshold</div>
        {% else %}
        <div class="result-status warning">⚠️ WARNING - Some images have warnings or unknown status</div>
        {% endif %}
    </div>
    
    <!-- Images Analyzed -->
    <div class="card">
        <h2>Images Analyzed</h2>
        <table>
            <tr>
                <th>#</th>
                <th>Image</th>
            </tr>
            {% for result in filtered_results %}
            <tr>
                <td>{{ loop.index }}</td>
                <td><code>{{ result.image }}</code></td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    <!-- Ignored Images -->
    {% if ignored_images %}
    <div class="card">
        <h2>Ignored Images</h2>
        <table>
            <tr>
                <th>#</th>
                <th>Image</th>
            </tr>
            {% for img in ignored_images %}
            <tr>
                <td>{{ loop.index }}</td>
                <td><code>{{ img }}</code></td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% endif %}
    
    <!-- Detailed Results -->
    <div class="card">
        <h2>Detailed Results</h2>
        <table>
            {% if has_repo_info %}
            <tr>
                <th>Image</th>
                <th>Repository</th>
                <th>Status</th>
                <th>Current</th>
                <th>Recommended</th>
                <th>Gap</th>
                <th>Message</th>
            </tr>
            {% for result in filtered_results %}
            <tr>
                <td><code>{{ result.image }}</code></td>
                <td>{{ result.repository }}</td>
                <td class="status-cell {{ 'success' if result.status == 'UP-TO-DATE' else 'danger' if result.status == 'OUTDATED' else 'warning' if result.status == 'WARNING' else 'unknown' }}">
                    <span class="badge badge-{{ 'success' if result.status == 'UP-TO-DATE' else 'danger' if result.status == 'OUTDATED' else 'warning' if result.status == 'WARNING' else 'unknown' }}">
                        {{ result.status }}
                    </span>
                </td>
                <td>{{ result.current|default('N/A') }}</td>
                <td>{{ result.recommended|default('N/A') }}</td>
                <td>{{ result.gap|default('N/A') }}</td>
                <td>{{ result.message }}</td>
            </tr>
            {% endfor %}
            {% elif github_info and github_info.repo %}
            <tr>
                <th>Image</th>
                <th>Repository</th>
                <th>Status</th>
                <th>Current</th>
                <th>Recommended</th>
                <th>Gap</th>
                <th>Message</th>
            </tr>
            {% for result in filtered_results %}
            <tr>
                <td><code>{{ result.image }}</code></td>
                <td>{{ github_info.repo }}</td>
                <td class="status-cell {{ 'success' if result.status == 'UP-TO-DATE' else 'danger' if result.status == 'OUTDATED' else 'warning' if result.status == 'WARNING' else 'unknown' }}">
                    <span class="badge badge-{{ 'success' if result.status == 'UP-TO-DATE' else 'danger' if result.status == 'OUTDATED' else 'warning' if result.status == 'WARNING' else 'unknown' }}">
                        {{ result.status }}
                    </span>
                </td>
                <td>{{ result.current|default('N/A') }}</td>
                <td>{{ result.recommended|default('N/A') }}</td>
                <td>{{ result.gap|default('N/A') }}</td>
                <td>{{ result.message }}</td>
            </tr>
            {% endfor %}
            {% else %}
            <tr>
                <th>Image</th>
                <th>Status</th>
                <th>Current</th>
                <th>Recommended</th>
                <th>Gap</th>
                <th>Message</th>
            </tr>
            {% for result in filtered_results %}
            <tr>
                <td><code>{{ result.image }}</code></td>
                <td class="status-cell {{ 'success' if result.status == 'UP-TO-DATE' else 'danger' if result.status == 'OUTDATED' else 'warning' if result.status == 'WARNING' else 'unknown' }}">
                    <span class="badge badge-{{ 'success' if result.status == 'UP-TO-DATE' else 'danger' if result.status == 'OUTDATED' else 'warning' if result.status == 'WARNING' else 'unknown' }}">
                        {{ result.status }}
                    </span>
                </td>
                <td>{{ result.current|default('N/A') }}</td>
                <td>{{ result.recommended|default('N/A') }}</td>
                <td>{{ result.gap|default('N/A') }}</td>
                <td>{{ result.message }}</td>
            </tr>
            {% endfor %}
            {% endif %}
        </table>
    </div>
    
    <!-- Security Section (if available) -->
    {% if has_security_info %}
    <div class="card">
        <h2>Security Scan Results</h2>
        
        <!-- Security Status Summary -->
        {% if security_status == 'VULNERABLE' %}
        <div class="result-status danger">⛔ VULNERABLE - Vulnerabilities found in one or more images</div>
        {% elif security_status == 'WARNING' %}
        <div class="result-status warning">⚠️ WARNING - Errors during security scan</div>
        {% else %}
        <div class="result-status success">✅ SECURE - No vulnerabilities found</div>
        {% endif %}
        
        <p>Images scanned for vulnerabilities: <strong>{{ security_scanned }}</strong></p>
        
        <!-- Vulnerable Images -->
        {% if vulnerable_images %}
        <h3>⛔ {{ vulnerable_images|length }} Vulnerable Image(s)</h3>
        <table>
            <tr>
                <th>Image</th>
                <th>Vulnerabilities</th>
                <th>Critical</th>
                <th>High</th>
                <th>Medium</th>
                <th>Low</th>
                <th>Fixable</th>
            </tr>
            {% for img in vulnerable_images %}
            <tr>
                <td><code>{{ img.image }}</code></td>
                <td>{{ img.security.summary.total }}</td>
                <td>{{ img.security.summary.severities.critical }}</td>
                <td>{{ img.security.summary.severities.high }}</td>
                <td>{{ img.security.summary.severities.medium }}</td>
                <td>{{ img.security.summary.severities.low }}</td>
                <td>{{ img.security.summary.fixable }}</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
        
        <!-- Secure Images -->
        {% if secure_images %}
        <h3>✅ {{ secure_images|length }} Secure Image(s)</h3>
        <table>
            <tr>
                <th>Image</th>
                <th>Status</th>
            </tr>
            {% for img in secure_images %}
            <tr>
                <td><code>{{ img.image }}</code></td>
                <td class="status-cell success">No vulnerabilities found</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
        
        <!-- Scan Errors -->
        {% if error_images %}
        <h3>❓ {{ error_images|length }} Error(s) During Scan</h3>
        <table>
            <tr>
                <th>Image</th>
                <th>Error</th>
            </tr>
            {% for img in error_images %}
            <tr>
                <td><code>{{ img.image }}</code></td>
                <td>{{ img.security.message }}</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
    </div>
    {% endif %}
    
    <footer>
        <p style="text-align: center; margin-top: 20px; color: var(--text-secondary);">
            Generated by Docker Image Version Analyzer
        </p>
    </footer>
</body>
</html>"""
    
    def format(self, results, total_images, original_count=None, github_info=None):
        """
        Format the results as HTML.
        
        Args:
            results: List of image analysis results
            total_images: Total number of images analyzed (after filtering)
            original_count: Original number of images before filtering (optional)
            github_info: Information about GitHub repository (optional)
            
        Returns:
            String representation of formatted results as HTML
        """
        # Get filtered results and ignored images
        filtered_results = [r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY']
        ignored_info = next((r for r in results if r.get('image') == 'IGNORED_IMAGES_SUMMARY'), None)
        ignored_images = ignored_info.get('ignored_images', []) if ignored_info else []
        
        # Get summary stats
        summary = self.get_summary(results)
        timestamp = self.get_timestamp()
        
        # Check if we have repository info in results
        has_repo_info = any('repository' in result for result in filtered_results)
        
        # Check if we have security info in results
        has_security_info = any('security' in result for result in filtered_results)
        security_status = None
        security_scanned = 0
        vulnerable_images = []
        secure_images = []
        error_images = []
        
        if has_security_info:
            # Count security statuses
            for result in filtered_results:
                if 'security' in result:
                    security_scanned += 1
                    if result['security']['status'] == 'VULNERABLE':
                        vulnerable_images.append(result)
                    elif result['security']['status'] == 'SECURE':
                        secure_images.append(result)
                    elif result['security']['status'] == 'ERROR':
                        error_images.append(result)
            
            # Determine overall security status
            if vulnerable_images:
                security_status = 'VULNERABLE'
            elif error_images:
                security_status = 'WARNING'
            else:
                security_status = 'SECURE'
        
        # Prepare context for the template
        context = {
            'filtered_results': filtered_results,
            'ignored_images': ignored_images,
            'summary': summary,
            'timestamp': timestamp,
            'github_info': github_info,
            'total_images': total_images,
            'original_count': original_count,
            'has_repo_info': has_repo_info,
            'has_security_info': has_security_info,
            'security_status': security_status,
            'security_scanned': security_scanned,
            'vulnerable_images': vulnerable_images,
            'secure_images': secure_images,
            'error_images': error_images
        }
        
        # Render the template
        template = self.jinja_env.get_template(self.TEMPLATE_FILE)
        return template.render(**context)


def get_formatter(format_type, include_timestamp=True):
    """
    Factory function to get the appropriate formatter.
    
    Args:
        format_type: Type of formatter ('text', 'json', 'csv', 'markdown', 'html')
        include_timestamp: Whether to include timestamp in the output
        
    Returns:
        Formatter instance
    """
    formatters = {
        'text': TextFormatter,
        'json': JsonFormatter,
        'csv': CsvFormatter,
        'markdown': MarkdownFormatter,
        'html': HtmlFormatter
    }
    
    formatter_class = formatters.get(format_type.lower(), TextFormatter)
    return formatter_class(include_timestamp=include_timestamp)