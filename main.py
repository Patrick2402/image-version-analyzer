#!/usr/bin/env python3
import re
import sys
import os.path
import json
import urllib.request
from packaging import version
from collections import defaultdict

# Import funkcji analizujących
from dockerfile_parser import extract_base_images
from image_analyzer import analyze_image_tags
from utils import parse_private_registries, load_custom_rules
from image_ignore import parse_ignore_options
from formatters import get_formatter
from slack_notifier import send_slack_notification

def main():
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print("Usage: python3 main.py <path_to_Dockerfile> [options]")
        print("Options:")
        print("  --tags: Show available tags for images")
        print("  --threshold N: Set the version gap threshold for marking images as outdated (default: 3)")
        print("  --level N: Force specific version level for comparison (1=major, 2=minor, 3=patch)")
        print("  --private-registry [REGISTRY]: Mark images from specified private registry")
        print("  --private-registries-file FILE: File containing list of private registries")
        print("  --rules FILE: JSON file with custom rules for specific images")
        
        # Output format options
        print("\nOutput Options:")
        print("  --output FORMAT: Specify output format (text, json, html, csv, markdown)")
        print("  --report-file PATH: Save analysis results to specified file")
        print("  --no-timestamp: Do not include timestamp in the report")
        
        # Image ignore options
        print("\nImage Ignore Options:")
        print("  --ignore PATTERN: Ignore specific image pattern (wildcards supported, can be specified multiple times)")
        print("  --ignore-images FILE: Path to file containing list of images to ignore")
        
        # Slack notification options
        print("\nSlack Notification Options:")
        print("  --slack-notify: Send notification to Slack about analysis results")
        print("  --slack-webhook URL: Webhook URL for Slack notifications (can also use SLACK_WEBHOOK_URL env variable)")
        print("  --report-url URL: Include a URL to a detailed report in the Slack notification")
        
        print("\nExample rules.json format:")
        print('''
{
  "node": {
    "level": 1,
    "lts_versions": [16, 18, 20, 22, 24],
    "step_by": 2,
    "skip_versions": ["19", "21", "23"]
  },
  "debian": {
    "level": 1
  }
}
''')
        print("\nExample ignore file format:")
        print('''
# Lines starting with # are comments
# Each line is a pattern to ignore
# Wildcard (*) is supported
python:3.9*
nginx:1.1*
# Use regex: prefix for regex patterns
regex:^debian:(?!11).*
''')
        return
    
    dockerfile_path = sys.argv[1]
    show_tags = "--tags" in sys.argv
    
    # Parse private registries
    private_registries = parse_private_registries(sys.argv)
    if private_registries:
        print("Using private registries:")
        for registry in private_registries:
            print(f"  - {registry}")
    
    # Parse custom rules
    custom_rules = {}
    if "--rules" in sys.argv:
        try:
            idx = sys.argv.index("--rules")
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
                rules_file = sys.argv[idx + 1]
                custom_rules = load_custom_rules(rules_file)
        except ValueError:
            pass
    
    # Parse ignore options
    ignore_manager = parse_ignore_options(sys.argv)
    
    # Parse threshold argument
    threshold = 3  # Default threshold
    for i, arg in enumerate(sys.argv):
        if arg == "--threshold" and i + 1 < len(sys.argv):
            try:
                threshold = int(sys.argv[i + 1])
                print(f"Using version gap threshold: {threshold}")
            except ValueError:
                print(f"Warning: Invalid threshold value. Using default: {threshold}")
    
    # Parse version level argument
    force_level = None
    for i, arg in enumerate(sys.argv):
        if arg == "--level" and i + 1 < len(sys.argv):
            try:
                level = int(sys.argv[i + 1])
                if 1 <= level <= 3:
                    force_level = level
                    level_name = {1: "major", 2: "minor", 3: "patch"}[level]
                    print(f"Forcing {level_name} version level ({level}) for all images")
                else:
                    print(f"Warning: Level must be between 1 and 3. Using automatic detection.")
            except ValueError:
                print(f"Warning: Invalid level value. Using automatic detection.")
    
    # Parse output format options
    output_format = 'text'  # Default
    report_file = None
    include_timestamp = True
    
    if '--output' in sys.argv:
        try:
            idx = sys.argv.index('--output')
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith('--'):
                output_format = sys.argv[idx + 1].lower()
                if output_format not in ['text', 'json', 'html', 'csv', 'markdown']:
                    print(f"Warning: Invalid output format '{output_format}'. Using 'text'.")
                    output_format = 'text'
        except (ValueError, IndexError):
            pass
    
    if '--report-file' in sys.argv:
        try:
            idx = sys.argv.index('--report-file')
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith('--'):
                report_file = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass
    
    if '--no-timestamp' in sys.argv:
        include_timestamp = False
    
    # Parse Slack notification options
    slack_webhook = None
    send_slack = False
    report_url = None
    
    if '--slack-notify' in sys.argv:
        send_slack = True
    
    if '--slack-webhook' in sys.argv:
        try:
            idx = sys.argv.index('--slack-webhook')
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith('--'):
                slack_webhook = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass
    
    if '--report-url' in sys.argv:
        try:
            idx = sys.argv.index('--report-url')
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith('--'):
                report_url = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass
    
    image_info_list = extract_base_images(dockerfile_path)
    
    if not image_info_list:
        print("No valid images found in Dockerfile.")
        sys.exit(1)
    
    # Filter out ignored images
    original_count = len(image_info_list)
    filtered_image_info_list = []
    ignored_images = []
    
    for info in image_info_list:
        if ignore_manager.should_ignore(info['image']):
            ignored_images.append(info['image'])
        else:
            filtered_image_info_list.append(info)
    
    # Print information about ignored images
    if ignored_images:
        print(f"Ignoring {len(ignored_images)} image(s):")
        for img in ignored_images:
            print(f"  - {img}")
    
    if not filtered_image_info_list:
        print("All images are ignored. Nothing to analyze.")
        sys.exit(0)
    
    # Update image_info_list to filtered version
    image_info_list = filtered_image_info_list
    total_images = len(image_info_list)
    
    # List images found in dockerfile but don't print yet if using non-text output
    if output_format == 'text':
        print(f"Found {total_images} image{'s' if total_images > 1 else ''} in Dockerfile:")
        for i, info in enumerate(image_info_list, 1):
            stage_info = f" (stage: {info['stage']})" if info['stage'] else ""
            print(f"{i}. {info['image']}{stage_info}")
    
    outdated_images = []
    warning_images = []
    unknown_images = []
    all_results = []
    
    if show_tags:
        # Redirect output to a buffer if not using text format
        original_stdout = sys.stdout
        if output_format != 'text':
            sys.stdout = open(os.devnull, 'w')  # Redirect to /dev/null
        
        for i, info in enumerate(image_info_list, 1):
            status = analyze_image_tags(
                info['image'], 
                i, 
                len(image_info_list), 
                threshold, 
                force_level,
                private_registries,
                custom_rules
            )
            
            all_results.append(status)
            
            if status['status'] == 'OUTDATED':
                outdated_images.append(status)
            elif status['status'] == 'WARNING':
                warning_images.append(status)
            elif status['status'] == 'UNKNOWN':
                unknown_images.append(status)
        
        # Restore stdout if it was redirected
        if output_format != 'text':
            sys.stdout.close()
            sys.stdout = original_stdout
    
    # Add ignored images info to the summary if any were ignored
    if ignored_images:
        all_results.append({
            'image': 'IGNORED_IMAGES_SUMMARY',
            'status': 'INFO',
            'message': f"{len(ignored_images)} image(s) were ignored",
            'ignored_images': ignored_images
        })
    
    # Create formatter and generate output
    formatter = get_formatter(output_format, include_timestamp=include_timestamp)
    formatted_output = formatter.format(all_results, total_images, original_count)
    
    # Save to file if specified
    if report_file:
        success = formatter.save_to_file(formatted_output, report_file)
        if success:
            print(f"Report saved to: {report_file}")
        else:
            print(f"Failed to save report to: {report_file}")
    
    # Print output if it's text format or no file was specified
    if output_format == 'text' or not report_file:
        print(formatted_output)
    
    # Send Slack notification if requested
    if send_slack:
        additional_info = {}
        if report_url:
            additional_info['report_url'] = report_url
        
        # Add CI/CD info if available
        if os.environ.get('CI_PIPELINE_URL'):
            additional_info['CI Pipeline'] = os.environ['CI_PIPELINE_URL']
        elif os.environ.get('GITHUB_WORKFLOW'):
            additional_info['GitHub Workflow'] = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}"
        
        # Send notification
        success = send_slack_notification(
            all_results,
            dockerfile_path,
            webhook_url=slack_webhook,
            additional_info=additional_info
        )
        
        if success:
            print("✅ Slack notification sent successfully")
        else:
            print("❌ Failed to send Slack notification")
    
    # Set exit code
    if not outdated_images and not warning_images and not unknown_images:
        sys.exit(0)  # All up-to-date
    elif outdated_images:
        sys.exit(1)  # Outdated images found
    else:
        sys.exit(0)  # Warnings only, but still considered successful

if __name__ == "__main__":
    main()