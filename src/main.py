#!/usr/bin/env python3
import argparse
import sys
import os.path
import json
import time
import re
from colorama import init, Fore, Style

from docker.dockerfile_parser import extract_base_images
from src.image_analyzer import analyze_image_tags
from utils.utils import parse_private_registries, load_custom_rules
from src.image_ignore import parse_ignore_options, ImageIgnoreManager
from utils.formatters import get_formatter
from utils.slack_notifier import send_slack_notification
from src.github_scanner import github_scan
from src.gitlab_scanner import gitlab_scan
from utils.registry_utils import get_image_tags, is_valid_version_tag


def parse_arguments():
    """Parse command line arguments with better handling using argparse"""
    parser = argparse.ArgumentParser(description="Docker Image Version Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # GitHub scanner subcommand
    github_parser = subparsers.add_parser("github-scan", help="Scan GitHub repositories")
    github_parser.add_argument("--github-token", help="GitHub API token")
    github_parser.add_argument("--github-org", help="GitHub organization name")
    github_parser.add_argument("--github-user", help="GitHub username")
    github_parser.add_argument("--output-dir", help="Directory to save reports", default="docker_analysis")
    github_parser.add_argument("--max-workers", type=int, help="Maximum number of concurrent workers", default=5)
    
    # GitLab scanner subcommand
    gitlab_parser = subparsers.add_parser("gitlab-scan", help="Scan GitLab repositories")
    gitlab_parser.add_argument("--gitlab-token", help="GitLab API token")
    gitlab_parser.add_argument("--gitlab-org", help="GitLab organization name")
    gitlab_parser.add_argument("--gitlab-user", help="GitLab username")
    gitlab_parser.add_argument("--output-dir", help="Directory to save reports", default="docker_analysis")
    gitlab_parser.add_argument("--max-workers", type=int, help="Maximum number of concurrent workers", default=5)
    
    # Main command for Dockerfile analysis
    main_parser = subparsers.add_parser("analyze", help="Analyze a Dockerfile")
    main_parser.add_argument("dockerfile", help="Path to Dockerfile")
    main_parser.add_argument("--tags", action="store_true", help="Show available tags for images")
    main_parser.add_argument("--threshold", type=int, default=3, help="Version gap threshold for marking images as outdated")
    main_parser.add_argument("--level", type=int, choices=[1, 2, 3], help="Force specific version level (1=major, 2=minor, 3=patch)")
    main_parser.add_argument("--private-registry", action="append", help="Mark images from specified private registry")
    main_parser.add_argument("--private-registries-file", help="File containing list of private registries")
    main_parser.add_argument("--rules", help="JSON file with custom rules for specific images")
    main_parser.add_argument("--no-info", action="store_true", help="Do not show detailed information about images")
    main_parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    
    # Output options
    output_group = main_parser.add_argument_group("Output Options")
    output_group.add_argument("--output", choices=["text", "json", "html", "csv", "markdown"], default="text", 
                             help="Specify output format")
    output_group.add_argument("--report-file", help="Save analysis results to specified file")
    output_group.add_argument("--no-timestamp", action="store_true", help="Do not include timestamp in the report")
    
    # Image ignore options
    ignore_group = main_parser.add_argument_group("Image Ignore Options")
    ignore_group.add_argument("--ignore", action="append", help="Ignore specific image pattern (can be specified multiple times)")
    ignore_group.add_argument("--ignore-images", help="Path to file containing list of images to ignore")
    
    # Slack notification options
    slack_group = main_parser.add_argument_group("Slack Notification Options")
    slack_group.add_argument("--slack-notify", action="store_true", help="Send notification to Slack about analysis results")
    slack_group.add_argument("--slack-webhook", help="Webhook URL for Slack notifications")
    slack_group.add_argument("--report-url", help="Include a URL to a detailed report in the Slack notification")
    
    # Add common options to all subparsers
    for subparser in [github_parser, gitlab_parser]:
        subparser.add_argument("--tags", action="store_true", help="Show available tags for images")
        subparser.add_argument("--threshold", type=int, default=3, help="Version gap threshold")
        subparser.add_argument("--level", type=int, choices=[1, 2, 3], help="Force specific version level")
        subparser.add_argument("--rules", help="JSON file with custom rules")
        subparser.add_argument("--output", choices=["text", "json", "html", "csv", "markdown"], default="html")
        subparser.add_argument("--no-timestamp", action="store_true", help="Do not include timestamp")
        subparser.add_argument("--ignore", action="append", help="Ignore specific image pattern")
        subparser.add_argument("--ignore-images", help="File with images to ignore")
        subparser.add_argument("--slack-notify", action="store_true", help="Send Slack notification")
        subparser.add_argument("--slack-webhook", help="Webhook URL for Slack")
        subparser.add_argument("--no-info", action="store_true", help="Do not show detailed information")
        subparser.add_argument("--no-color", action="store_true", help="Disable colored output")
    
    # Handle the case when no arguments are provided
    if len(sys.argv) == 1:
        # Default to analyze subcommand when no command is specified
        sys.argv.append("analyze")
    
    # Handle default analyze command when only providing a Dockerfile path
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ["analyze", "github-scan", "gitlab-scan", "--help", "-h"]:
        dockerfile_path = sys.argv[1]
        sys.argv[1] = "analyze"
        sys.argv.insert(2, dockerfile_path)
    
    return parser.parse_args()


def setup_ignore_manager(args):
    """Set up the image ignore manager from arguments"""
    ignore_manager = ImageIgnoreManager()
    
    # Add patterns from --ignore arguments
    if args.ignore:
        for pattern in args.ignore:
            ignore_manager.add_pattern(pattern)
    
    # Add patterns from --ignore-images file
    if args.ignore_images:
        ignore_manager.load_patterns_from_file(args.ignore_images)
    
    return ignore_manager


def filter_similar_tags(tags, current_tag):
    """Filter tags to show only ones similar to current tag"""
    if not current_tag:
        return tags
        
    # Extract variant from current tag if it exists
    current_variant = None
    variant_match = re.match(r'^v?\d+(\.\d+)*(-(.+))?$', current_tag)
    if variant_match and variant_match.group(2):
        current_variant = variant_match.group(3)
    
    # If we have a variant, filter to show only tags with same variant
    if current_variant:
        similar_tags = [tag for tag in tags if f"-{current_variant}" in tag]
        if similar_tags:
            return similar_tags
    
    # If we have a 'v' prefix, filter to show tags with same prefix pattern
    if current_tag.startswith('v'):
        v_tags = [tag for tag in tags if tag.startswith('v')]
        if v_tags:
            return v_tags
    
    # Otherwise, show clean version tags without variants when possible
    clean_tags = []
    for tag in tags:
        # Try to find tags that are just version numbers
        if re.match(r'^v?\d+(\.\d+)*$', tag):
            clean_tags.append(tag)
    
    if clean_tags:
        return clean_tags
    
    # Fallback to all valid version tags
    return tags


def analyze_dockerfile(args):
    """Analyze a Dockerfile based on the provided arguments"""
    # Initialize colorama for colored terminal output
    init(autoreset=True)
    if args.no_color:
        init(autoreset=True, strip=True)
    
    # Print header
    if not args.no_color:
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║            Docker Image Version Analyzer v1.4.0                  ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    else:
        print("\n=================================================================")
        print("                Docker Image Version Analyzer                     ")
        print("=================================================================")
    
    # Get private registries
    private_registries = []
    
    if args.private_registry:
        private_registries.extend(args.private_registry)
    
    if args.private_registries_file:
        try:
            with open(args.private_registries_file, 'r') as f:
                for line in f:
                    registry = line.strip()
                    if registry and not registry.startswith('#'):
                        private_registries.append(registry)
        except Exception as e:
            print(f"{Fore.YELLOW if not args.no_color else ''}Error reading private registries file: {e}{Style.RESET_ALL if not args.no_color else ''}")
    
    if private_registries:
        print(f"{Fore.BLUE if not args.no_color else ''}• Using private registries:{Style.RESET_ALL if not args.no_color else ''}")
        for registry in private_registries:
            print(f"  - {registry}")
    
    # Load custom rules
    custom_rules = {}
    if args.rules:
        custom_rules = load_custom_rules(args.rules)
        if custom_rules:
            print(f"{Fore.BLUE if not args.no_color else ''}• Loaded {len(custom_rules)} custom rules{Style.RESET_ALL if not args.no_color else ''}")
    
    # Display threshold
    print(f"{Fore.BLUE if not args.no_color else ''}• Version threshold: {args.threshold}{Style.RESET_ALL if not args.no_color else ''}")
    
    # Set up ignore manager
    ignore_manager = setup_ignore_manager(args)
    if ignore_manager.get_patterns():
        print(f"{Fore.BLUE if not args.no_color else ''}• Using {len(ignore_manager.get_patterns())} ignore patterns{Style.RESET_ALL if not args.no_color else ''}")
    
    # Extract images from Dockerfile
    start_time = time.time()
    print(f"\n{Fore.BLUE if not args.no_color else ''}• Analyzing {args.dockerfile}{Style.RESET_ALL if not args.no_color else ''}")
    
    try:
        image_info_list = extract_base_images(args.dockerfile, no_info=args.no_info)
    except Exception as e:
        print(f"{Fore.RED if not args.no_color else ''}Error parsing Dockerfile: {e}{Style.RESET_ALL if not args.no_color else ''}")
        return 1
    
    if not image_info_list:
        print(f"{Fore.YELLOW if not args.no_color else ''}No valid images found in Dockerfile.{Style.RESET_ALL if not args.no_color else ''}")
        return 1
    
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
        print(f"{Fore.YELLOW if not args.no_color else ''}• Ignoring {len(ignored_images)} image(s):{Style.RESET_ALL if not args.no_color else ''}")
        for img in ignored_images:
            print(f"  - {img}")
    
    if not filtered_image_info_list:
        print(f"{Fore.YELLOW if not args.no_color else ''}All images are ignored. Nothing to analyze.{Style.RESET_ALL if not args.no_color else ''}")
        return 0
    
    # Update image_info_list to filtered version
    image_info_list = filtered_image_info_list
    total_images = len(image_info_list)
    
    # List images found in Dockerfile
    print(f"\n{Fore.GREEN if not args.no_color else ''}Found {total_images} image{'s' if total_images > 1 else ''} in Dockerfile:{Style.RESET_ALL if not args.no_color else ''}")
    for i, info in enumerate(image_info_list, 1):
        stage_info = f" {Fore.BLUE if not args.no_color else ''}(stage: {info['stage']}){Style.RESET_ALL if not args.no_color else ''}" if info['stage'] else ""
        print(f"{Fore.WHITE if not args.no_color else ''}{i}. {info['image']}{stage_info}{Style.RESET_ALL if not args.no_color else ''}")
    
    # Analyze each image
    outdated_images = []
    warning_images = []
    unknown_images = []
    all_results = []
    
    # Always perform the analysis
    for i, info in enumerate(image_info_list, 1):
        # Extract current tag from image name for later use with tag filtering
        parts = info['image'].split(':')
        current_tag = parts[1] if len(parts) > 1 else None
        
        # Analyze the image using the original function
        print(f"\n{Fore.CYAN if not args.no_color else ''}Analyzing image {i}/{total_images}: {info['image']}{Style.RESET_ALL if not args.no_color else ''}")
        
        # Perform the original analysis
        status = analyze_image_tags(
            info['image'],
            i,
            total_images,
            args.threshold,
            args.level,
            private_registries,
            custom_rules,
            not args.tags  # no_info is the opposite of show_tags
        )
        
        # Add custom tag filtering if tags option is enabled
        if args.tags and not args.no_info and current_tag:
            # Get tags from registry
            tags, _ = get_image_tags(info['image'], private_registries)
            
            if tags:
                # Filter to valid version tags first
                version_tags = [tag for tag in tags if is_valid_version_tag(tag)]
                
                # Then filter to similar tags
                relevant_tags = filter_similar_tags(version_tags, current_tag)
                
                # Sort and display
                if relevant_tags:
                    sample_size = min(5, len(relevant_tags))
                    sorted_tags = sorted(relevant_tags)[:sample_size]
                    print(f"{Fore.BLUE if not args.no_color else ''}• Similar tags: {', '.join(sorted_tags)}" + 
                          (f" + {len(relevant_tags) - sample_size} more" if len(relevant_tags) > sample_size else ""))
        
        all_results.append(status)
        
        if status['status'] == 'OUTDATED':
            outdated_images.append(status)
        elif status['status'] == 'WARNING':
            warning_images.append(status)
        elif status['status'] == 'UNKNOWN':
            unknown_images.append(status)
    
    # Add ignored images info to the summary if any were ignored
    if ignored_images:
        all_results.append({
            'image': 'IGNORED_IMAGES_SUMMARY',
            'status': 'INFO',
            'message': f"{len(ignored_images)} image(s) were ignored",
            'ignored_images': ignored_images
        })
    
    # Show pretty summary table
    if args.output == 'text' and not args.report_file:
        # Header for summary
        if not args.no_color:
            print(f"\n{Fore.CYAN}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{Style.RESET_ALL}")
            print(f"{Fore.CYAN}                         ANALYSIS SUMMARY                          {Style.RESET_ALL}")
            print(f"{Fore.CYAN}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{Style.RESET_ALL}")
        else:
            print("\n==================================================================")
            print("                       ANALYSIS SUMMARY                            ")
            print("==================================================================")
        
        # Table header using fixed widths
        if not args.no_color:
            print(f"{Fore.WHITE}{'IMAGE':<40} {'STATUS':<20} {'CURRENT':<15} {'→':2} {'RECOMMENDED':<15} {'MESSAGE'}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'-' * 100}{Style.RESET_ALL}")
        else:
            print(f"{'IMAGE':<40} {'STATUS':<20} {'CURRENT':<15} → {'RECOMMENDED':<15} {'MESSAGE'}")
            print(f"{'-' * 100}")
        
        # Print each result in a table row
        for result in all_results:
            # Skip special entries
            if result.get('image') == 'IGNORED_IMAGES_SUMMARY':
                continue
                
            # Format image name
            image_name = result['image']
            if len(image_name) > 37:
                image_name = image_name[:34] + "..."
            
            # Format status
            status = result['status']
            if not args.no_color:
                if status == 'UP-TO-DATE':
                    status_display = f"{Fore.GREEN}✓ {status}{Style.RESET_ALL}"
                elif status == 'OUTDATED':
                    status_display = f"{Fore.RED}✗ {status}{Style.RESET_ALL}"
                elif status == 'WARNING':
                    status_display = f"{Fore.YELLOW}⚠ {status}{Style.RESET_ALL}"
                else:
                    status_display = f"{Fore.YELLOW}? {status}{Style.RESET_ALL}"
            else:
                if status == 'UP-TO-DATE':
                    status_display = f"✓ {status}"
                elif status == 'OUTDATED':
                    status_display = f"✗ {status}"
                elif status == 'WARNING':
                    status_display = f"⚠ {status}"
                else:
                    status_display = f"? {status}"
            
            # Format version
            current = result.get('current', '-')
            recommended = result.get('recommended', '-')
            
            # Format message
            message = result.get('message', '')
            
            # Print the row with fixed column widths
            print(f"{image_name:<40} {status_display:<20} {current:<15} → {recommended:<15} {message}")
        
        # Table footer
        if not args.no_color:
            print(f"{Fore.CYAN}{'-' * 100}{Style.RESET_ALL}")
        else:
            print(f"{'-' * 100}")
        
        # Final verdict
        if outdated_images:
            if not args.no_color:
                print(f"\n{Fore.RED}✗ RESULT: OUTDATED - {len(outdated_images)} image(s) need updating{Style.RESET_ALL}")
            else:
                print(f"\n✗ RESULT: OUTDATED - {len(outdated_images)} image(s) need updating")
        elif warning_images or unknown_images:
            if not args.no_color:
                print(f"\n{Fore.YELLOW}⚠ RESULT: WARNING - {len(warning_images) + len(unknown_images)} image(s) with warnings{Style.RESET_ALL}")
            else:
                print(f"\n⚠ RESULT: WARNING - {len(warning_images) + len(unknown_images)} image(s) with warnings")
        else:
            if not args.no_color:
                print(f"\n{Fore.GREEN}✓ RESULT: SUCCESS - All images are up-to-date{Style.RESET_ALL}")
            else:
                print(f"\n✓ RESULT: SUCCESS - All images are up-to-date")
        
        # Show execution time
        elapsed = time.time() - start_time
        print(f"\nAnalysis completed in {elapsed:.2f} seconds")
    else:
        # Create formatter and generate output
        formatter = get_formatter(args.output, include_timestamp=not args.no_timestamp)
        formatted_output = formatter.format(all_results, total_images, original_count)
        
        # Save to file if specified
        if args.report_file:
            success = formatter.save_to_file(formatted_output, args.report_file)
            if success:
                print(f"\n{Fore.GREEN if not args.no_color else ''}✓ Report saved to: {args.report_file}{Style.RESET_ALL if not args.no_color else ''}")
            else:
                print(f"\n{Fore.RED if not args.no_color else ''}✗ Failed to save report to: {args.report_file}{Style.RESET_ALL if not args.no_color else ''}")
        
        # Print output if it's text format or no file was specified
        if args.output == 'text' or not args.report_file:
            print(formatted_output)
    
    # Send Slack notification if requested
    if args.slack_notify:
        additional_info = {}
        if args.report_url:
            additional_info['report_url'] = args.report_url
        
        # Add CI/CD info if available
        if os.environ.get('CI_PIPELINE_URL'):
            additional_info['CI Pipeline'] = os.environ['CI_PIPELINE_URL']
        elif os.environ.get('GITHUB_WORKFLOW'):
            additional_info['GitHub Workflow'] = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}"
        
        # Send notification
        webhook_url = args.slack_webhook or os.environ.get('SLACK_WEBHOOK_URL')
        success = send_slack_notification(
            all_results,
            args.dockerfile,
            webhook_url=webhook_url,
            additional_info=additional_info
        )
        
        if success:
            print(f"{Fore.GREEN if not args.no_color else ''}✓ Slack notification sent successfully{Style.RESET_ALL if not args.no_color else ''}")
        else:
            print(f"{Fore.RED if not args.no_color else ''}✗ Failed to send Slack notification{Style.RESET_ALL if not args.no_color else ''}")
    
    # Return exit code
    if outdated_images:
        return 1  # Outdated images found
    elif warning_images or unknown_images:
        return 0  # Warnings only, still considered successful
    else:
        return 0  # All up-to-date


def main():
    """Main entry point for the application"""
    args = parse_arguments()
    
    if args.command == "github-scan":
        # Convert argparse namespace to list of args for backward compatibility
        github_args = []
        for key, value in vars(args).items():
            if key != "command" and value is not None:
                if isinstance(value, bool) and value:
                    github_args.append(f"--{key}")
                elif not isinstance(value, bool):
                    github_args.append(f"--{key}")
                    github_args.append(str(value))
        
        return github_scan(github_args)
    
    elif args.command == "gitlab-scan":
        # Convert argparse namespace to list of args for backward compatibility
        gitlab_args = []
        for key, value in vars(args).items():
            if key != "command" and value is not None:
                if isinstance(value, bool) and value:
                    gitlab_args.append(f"--{key}")
                elif not isinstance(value, bool):
                    gitlab_args.append(f"--{key}")
                    github_args.append(str(value))
        
        return gitlab_scan(gitlab_args)
    
    elif args.command == "analyze":
        return analyze_dockerfile(args)
    
    else:
        print("No valid command specified. Use --help for usage information.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)