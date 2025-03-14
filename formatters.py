import json
import csv
import os
import io
from datetime import datetime

class BaseFormatter:
    """Base class for all formatters"""
    
    def __init__(self, include_timestamp=True):
        self.include_timestamp = include_timestamp
    
    def format(self, results, total_images):
        """
        Format the results.
        
        Args:
            results: List of image analysis results
            total_images: Total number of images analyzed
            
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
        outdated = [r for r in results if r['status'] == 'OUTDATED']
        warnings = [r for r in results if r['status'] == 'WARNING']
        unknown = [r for r in results if r['status'] == 'UNKNOWN']
        up_to_date = [r for r in results if r['status'] == 'UP-TO-DATE']
        
        return {
            'total': len(results),
            'outdated': len(outdated),
            'warnings': len(warnings),
            'unknown': len(unknown),
            'up_to_date': len(up_to_date),
            'outdated_images': outdated,
            'warning_images': warnings,
            'unknown_images': unknown,
            'up_to_date_images': up_to_date
        }


class TextFormatter(BaseFormatter):
    """Format results as plain text"""
    
    def format(self, results, total_images):
        output = []
        
        # Add timestamp
        timestamp = self.get_timestamp()
        if timestamp:
            output.append(f"Analysis Time: {timestamp}\n")
        
        output.append(f"Found {total_images} image(s) in Dockerfile:")
        for i, result in enumerate(results, 1):
            output.append(f"{i}. {result['image']}")
        
        output.append("\n" + "="*50)
        output.append("ANALYSIS SUMMARY")
        output.append("="*50)
        
        summary = self.get_summary(results)
        
        if summary['outdated'] > 0:
            output.append(f"\n⛔ {summary['outdated']} OUTDATED IMAGE(S):")
            for img in summary['outdated_images']:
                output.append(f"  - {img['image']} : {img['message']}")
        
        if summary['warnings'] > 0:
            output.append(f"\n⚠️ {summary['warnings']} WARNING(S):")
            for img in summary['warning_images']:
                output.append(f"  - {img['image']} : {img['message']}")
        
        if summary['unknown'] > 0:
            output.append(f"\n❓ {summary['unknown']} UNKNOWN STATUS:")
            for img in summary['unknown_images']:
                output.append(f"  - {img['image']} : {img['message']}")
        
        if not summary['outdated'] and not summary['warnings'] and not summary['unknown']:
            output.append("\n✅ ALL IMAGES UP-TO-DATE")
        elif summary['outdated']:
            output.append("\n⛔ RESULT: OUTDATED - At least one image is outdated beyond threshold")
        else:
            output.append("\n⚠️ RESULT: WARNING - Some images have warnings or unknown status")
        
        return "\n".join(output)


class JsonFormatter(BaseFormatter):
    """Format results as JSON"""
    
    def format(self, results, total_images):
        output = {
            'total_images': total_images,
            'results': results,
            'summary': self.get_summary(results),
        }
        
        timestamp = self.get_timestamp()
        if timestamp:
            output['timestamp'] = timestamp
        
        return json.dumps(output, indent=2)


class CsvFormatter(BaseFormatter):
    """Format results as CSV"""
    
    def format(self, results, total_images):
        output = io.StringIO()
        fieldnames = ['image', 'status', 'current', 'recommended', 'gap', 'message']
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            # Create a new row with only the fields we want
            row = {field: result.get(field, '') for field in fieldnames}
            writer.writerow(row)
        
        return output.getvalue()


class MarkdownFormatter(BaseFormatter):
    """Format results as Markdown"""
    
    def format(self, results, total_images):
        output = []
        
        # Add title and timestamp
        output.append("# Docker Image Analysis Report")
        
        timestamp = self.get_timestamp()
        if timestamp:
            output.append(f"*Generated on: {timestamp}*\n")
        
        # Images found
        output.append(f"## Found {total_images} image(s)")
        
        output.append("| # | Image |")
        output.append("| --- | --- |")
        for i, result in enumerate(results, 1):
            output.append(f"| {i} | `{result['image']}` |")
        
        # Summary
        output.append("\n## Analysis Summary")
        
        summary = self.get_summary(results)
        
        # Results table
        output.append("\n### Detailed Results")
        output.append("| Image | Status | Current | Recommended | Gap | Message |")
        output.append("| --- | --- | --- | --- | --- | --- |")
        
        for result in results:
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
                output.append(f"- `{img['image']}`: {current} → {recommended} ({img['message']})")
        else:
            output.append("⚠️ **RESULT: WARNING** - Some images have warnings or unknown status")
        
        return "\n".join(output)


class HtmlFormatter(BaseFormatter):
    """Format results as HTML"""
    
    def format(self, results, total_images):
        summary = self.get_summary(results)
        timestamp = self.get_timestamp()
        
        # Inline CSS for basic styling
        css = """
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 1200px; margin: 0 auto; }
            h1, h2, h3 { color: #333; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
            .success { background-color: #dff0d8; }
            .danger { background-color: #f2dede; }
            .warning { background-color: #fcf8e3; }
            .unknown { background-color: #e7e7e7; }
            .success-text { color: #3c763d; }
            .danger-text { color: #a94442; }
            .warning-text { color: #8a6d3b; }
            .badge { padding: 3px 8px; border-radius: 3px; font-size: 0.8em; color: white; display: inline-block; }
            .badge-success { background-color: #5cb85c; }
            .badge-danger { background-color: #d9534f; }
            .badge-warning { background-color: #f0ad4e; }
            .badge-unknown { background-color: #777; }
            pre { background-color: #f5f5f5; padding: 10px; border-radius: 4px; }
            .container { display: flex; justify-content: space-between; }
            .summary { flex: 1; margin-right: 20px; }
            .stats { flex: 1; }
        </style>
        """
        
        # Start HTML document
        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "<title>Docker Image Analysis Report</title>",
            css,
            "</head>",
            "<body>",
            "<h1>Docker Image Analysis Report</h1>"
        ]
        
        # Add timestamp
        if timestamp:
            html.append(f"<p><em>Generated on: {timestamp}</em></p>")
        
        # Add summary counts
        html.append("<div class='container'>")
        html.append("<div class='summary'>")
        html.append(f"<h2>Summary</h2>")
        html.append(f"<p>Found <strong>{total_images}</strong> image(s) in Dockerfile</p>")
        html.append("<ul>")
        html.append(f"<li><span class='badge badge-success'>Up-to-date</span> {summary['up_to_date']} images</li>")
        html.append(f"<li><span class='badge badge-danger'>Outdated</span> {summary['outdated']} images</li>")
        html.append(f"<li><span class='badge badge-warning'>Warning</span> {summary['warnings']} images</li>")
        html.append(f"<li><span class='badge badge-unknown'>Unknown</span> {summary['unknown']} images</li>")
        html.append("</ul>")
        html.append("</div>")
        
        # Add result status
        html.append("<div class='stats'>")
        html.append("<h2>Result</h2>")
        if not summary['outdated'] and not summary['warnings'] and not summary['unknown']:
            html.append("<p class='success-text'>✅ <strong>ALL IMAGES UP-TO-DATE</strong></p>")
        elif summary['outdated']:
            html.append("<p class='danger-text'>⛔ <strong>OUTDATED</strong> - At least one image is outdated beyond threshold</p>")
        else:
            html.append("<p class='warning-text'>⚠️ <strong>WARNING</strong> - Some images have warnings or unknown status</p>")
        html.append("</div>")
        html.append("</div>")
        
        # Images table
        html.append("<h2>Images Found</h2>")
        html.append("<table>")
        html.append("<tr><th>#</th><th>Image</th></tr>")
        for i, result in enumerate(results, 1):
            html.append(f"<tr><td>{i}</td><td><code>{result['image']}</code></td></tr>")
        html.append("</table>")
        
        # Detailed results
        html.append("<h2>Detailed Results</h2>")
        html.append("<table>")
        html.append("<tr><th>Image</th><th>Status</th><th>Current</th><th>Recommended</th><th>Gap</th><th>Message</th></tr>")
        
        for result in results:
            status_class = ""
            if result['status'] == 'UP-TO-DATE':
                status_class = "success"
                status_badge = "<span class='badge badge-success'>UP-TO-DATE</span>"
            elif result['status'] == 'OUTDATED':
                status_class = "danger"
                status_badge = "<span class='badge badge-danger'>OUTDATED</span>"
            elif result['status'] == 'WARNING':
                status_class = "warning"
                status_badge = "<span class='badge badge-warning'>WARNING</span>"
            else:
                status_class = "unknown"
                status_badge = "<span class='badge badge-unknown'>UNKNOWN</span>"
            
            current = result.get('current', 'N/A')
            recommended = result.get('recommended', 'N/A')
            gap = str(result.get('gap', 'N/A'))
            
            html.append(f"<tr class='{status_class}'>")
            html.append(f"<td><code>{result['image']}</code></td>")
            html.append(f"<td>{status_badge}</td>")
            html.append(f"<td>{current}</td>")
            html.append(f"<td>{recommended}</td>")
            html.append(f"<td>{gap}</td>")
            html.append(f"<td>{result['message']}</td>")
            html.append("</tr>")
        
        html.append("</table>")
        
        # End HTML document
        html.append("</body>")
        html.append("</html>")
        
        return "\n".join(html)


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