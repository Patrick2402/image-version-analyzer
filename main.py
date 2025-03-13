#!/usr/bin/env python3
import re
import sys
import os.path
import json
import urllib.request
from packaging import version
from collections import defaultdict

def extract_base_images(dockerfile_path):
    """Extracts all base images from a Dockerfile, including multiple FROM instructions."""
    try:
        if not os.path.isfile(dockerfile_path):
            print(f"Error: File {dockerfile_path} not found.")
            return []
            
        with open(dockerfile_path, 'r') as dockerfile:
            content = dockerfile.read()
            pattern = r'^\s*FROM\s+(--platform=[^\s]+\s+)?([^\s]+)(\s+AS\s+[^\s]+)?'
            
            images = []
            for line in content.split('\n'):
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    image_name = match.group(2)
                    stage_name = match.group(3).strip() if match.group(3) else None
                    images.append({
                        'image': image_name,
                        'stage': stage_name
                    })
            
            if not images:
                print("FROM instruction not found in Dockerfile")
                return []
            
            return images
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

def get_public_image_name(image_name, private_registries=None):
    """
    Extract public image name from a private registry image name.
    
    Args:
        image_name: Full image name
        private_registries: List of private registry prefixes to check
    
    Returns:
        str: Public image name without registry prefix if applicable
    """
    if not private_registries:
        return image_name
    
    for registry in private_registries:
        if registry in image_name:
            # Remove registry prefix
            parts = image_name.split('/')
            # Find the index where the registry prefix ends
            registry_parts = registry.split('/')
            registry_base = registry_parts[0]  # Get the domain part
            
            for i, part in enumerate(parts):
                if registry_base in part:
                    # Remove all parts up to and including this one
                    public_image = '/'.join(parts[i+1:])
                    print(f"Removing private registry prefix '{registry}', using: {public_image}")
                    return public_image
    
    return image_name

def is_supported_registry(image_name):
    """Check if the image is from a supported registry."""
    unsupported_registries = [
        "gcr.io",
        "k8s.gcr.io",
        "asia.gcr.io",
        "eu.gcr.io",
        "us.gcr.io",
        "ghcr.io",
        "quay.io",
        "ecr.aws"
    ]
    
    for registry in unsupported_registries:
        if registry in image_name:
            return False, registry
    
    return True, None

def get_image_tags(image_name, private_registries=None):
    """Fetches tags for an image and finds the best available version."""
    # Check if the registry is supported
    is_supported, registry_name = is_supported_registry(image_name)
    if not is_supported:
        print(f"Warning: {registry_name} is not supported for tag checking.")
        print(f"Cannot check for updates of {image_name}")
        print("Only Docker Hub images are currently supported.")
        return [], None
        
    # Get public image name regardless of whether it's from a private registry
    public_image = get_public_image_name(image_name, private_registries)
    # Split image and tag
    parts = public_image.split(':')
    image = parts[0]
    current_tag = parts[1] if len(parts) > 1 else None
    
    # Prepare for Docker Hub API
    if '/' not in image:
        image = f"library/{image}"
    
    try:
        url = f"https://hub.docker.com/v2/repositories/{image}/tags?page_size=100"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            tags = [tag['name'] for tag in data.get('results', [])]
            
            recommended_tag = find_recommended_tag(tags, current_tag)
            
            return tags, recommended_tag
    except Exception as e:
        print(f"Error during fetching tags: {str(e)}")
        return [], None

def is_valid_version_tag(tag):
    """Check if a tag looks like a valid semantic version and not a date or other numeric ID."""
    # Skip tags that are just long numbers (like dates: 20220101)
    if re.match(r'^\d{6,}$', tag):
        return False
        
    # Skip tags with too many numeric segments (probably not a version)
    if len(re.findall(r'\d+', tag)) > 4:
        return False
    
    # Skip tags with too many digits in total (probably a date or ID)
    total_digits = sum(len(digit) for digit in re.findall(r'\d+', tag))
    if total_digits > 8:
        return False
    
    # Acceptable patterns for versions
    # Examples: 3.19, v2.1.0, 1.24-alpine
    return re.match(r'^v?\d+(\.\d+){0,3}(-[a-z0-9]+)?$', tag) is not None

def load_custom_rules(rules_file):
    """Load custom rules from a JSON file."""
    if not os.path.isfile(rules_file):
        print(f"Warning: Rules file {rules_file} not found.")
        return {}
    
    try:
        with open(rules_file, 'r') as f:
            rules = json.load(f)
            print(f"Loaded custom rules for {len(rules)} images")
            return rules
    except Exception as e:
        print(f"Error loading rules file: {e}")
        return {}

def detect_version_level(tags, base_image_name, custom_rules=None):
    """
    Automatically detect the significant version level for an image by analyzing its tags.
    Uses custom rules if provided.
    
    Returns:
        int: The significant version level (1, 2, or 3)
    """
    # Default to level 1 (major version only)
    default_level = 1
    
    # Special handling for known images
    image_base = base_image_name.split('/')[-1]  # Get last part of image name (e.g., 'debian' from 'library/debian')
    
    # Check custom rules first if provided
    if custom_rules and image_base in custom_rules:
        rule = custom_rules[image_base]
        if "level" in rule:
            print(f"Using custom version level for {image_base}: {rule['level']}")
            return rule["level"]
    
    # Special cases based on image name
    special_cases = {
        'debian': 1,       # Debian uses x.y where x is the major release
        'ubuntu': 1,       # Ubuntu uses YY.MM format
        'centos': 1,       # CentOS uses single digit versions
        'alpine': 2,       # Alpine has frequent minor version updates (3.18, 3.19, etc.)
        'nginx': 2,        # nginx stays on 1.x for a long time
        'node': 1,         # Node.js has meaningful major versions (14, 16, 18, etc.)
        'python': 2,       # Python has meaningful minor versions (3.9, 3.10, etc.)
        'php': 2,          # PHP has meaningful minor versions (8.0, 8.1, etc.)
        'golang': 2,       # Go has meaningful minor versions (1.18, 1.19, etc.)
        'postgres': 2,     # PostgreSQL has meaningful minor versions (14.1, 14.2, etc.)
        'mysql': 1,        # MySQL major versions are significant (5.x, 8.x)
        'mariadb': 2,      # MariaDB has meaningful minor versions (10.5, 10.6, etc.)
        'mongo': 2,        # MongoDB has meaningful minor versions (4.4, 5.0, etc.)
        'redis': 2,        # Redis has meaningful minor versions (6.2, 7.0, etc.)
    }
    
    if image_base in special_cases:
        return special_cases[image_base]
    
    # Filter to just version tags
    version_tags = [tag for tag in tags if is_valid_version_tag(tag)]
    if not version_tags:
        return default_level
    
    # Analyze version patterns to detect significant level
    pattern_counts = defaultdict(int)
    
    for tag in version_tags:
        # Remove v prefix if present
        clean_tag = tag[1:] if tag.startswith('v') else tag
        
        # Remove suffix (like -alpine)
        clean_tag = re.sub(r'-.*$', '', clean_tag)
        
        # Count dots to determine version pattern
        parts = clean_tag.split('.')
        pattern = len(parts)
        pattern_counts[pattern] += 1
    
    # Check version difference patterns
    if len(version_tags) > 1:
        try:
            # Parse versions
            parsed_versions = []
            for tag in version_tags:
                clean_tag = tag[1:] if tag.startswith('v') else tag
                clean_tag = re.sub(r'-.*$', '', clean_tag)
                try:
                    v = version.parse(clean_tag)
                    parsed_versions.append((v, clean_tag))
                except:
                    pass
            
            if parsed_versions:
                # Sort by version
                sorted_versions = sorted(parsed_versions, key=lambda x: x[0])
                
                # Analyze version changes
                level_changes = defaultdict(int)
                
                for i in range(1, len(sorted_versions)):
                    prev_parts = sorted_versions[i-1][1].split('.')
                    curr_parts = sorted_versions[i][1].split('.')
                    
                    # Ensure we have at least 3 parts for comparison
                    while len(prev_parts) < 3:
                        prev_parts.append('0')
                    while len(curr_parts) < 3:
                        curr_parts.append('0')
                    
                    # Check which parts changed
                    for j in range(min(3, len(prev_parts))):
                        if prev_parts[j] != curr_parts[j]:
                            level_changes[j+1] += 1
                            break
                
                # Determine most common change level
                if level_changes:
                    most_common_level = max(level_changes.items(), key=lambda x: x[1])[0]
                    return most_common_level
        except Exception as e:
            print(f"Error in version pattern analysis: {e}")
    
    # If we can't determine a pattern, use most common format
    if pattern_counts:
        most_common_pattern = max(pattern_counts.items(), key=lambda x: x[1])[0]
        if most_common_pattern == 1:
            return 1  # Just major version
        elif most_common_pattern == 2:
            return 2  # Major.minor
        else:
            return 2  # Default to 2 levels for 3+ part versions
    
    return default_level

def find_recommended_tag(tags, current_tag=None):
    """Finds the newest numeric version from available tags."""
    if not tags:
        return None
    
    # For tags with 'v' prefix, separate the base versions from variants
    clean_tags = {}
    
    for tag in tags:
        # Skip development/test versions
        if any(x in tag for x in ['alpha', 'beta', 'rc', 'dev', 'test']):
            continue
            
        # Try to match the pattern for versioned tags
        match = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', tag)
        if match:
            # Extract the base version (without variants like -debug, -arm64v8)
            base_version = match.group(1)
            
            # Additional validation for version tags
            if not is_valid_version_tag(base_version):
                continue
                
            # Save the original tag for later retrieval
            if base_version not in clean_tags:
                clean_tags[base_version] = tag
    
    # Process the clean base versions to find the newest
    numeric_versions = []
    for base_version in clean_tags.keys():
        try:
            # Remove 'v' prefix for version comparison if present
            version_str = base_version[1:] if base_version.startswith('v') else base_version
            v = version.parse(version_str)
            numeric_versions.append((v, clean_tags[base_version]))
        except:
            pass
    
    # Return the tag with the newest version
    if numeric_versions:
        return sorted(numeric_versions, key=lambda x: x[0])[-1][1]
    
    # Fallbacks if no clean numeric versions found
    if 'stable' in tags:
        return 'stable'
    
    for tag in tags:
        if tag != 'latest':
            return tag
    
    return tags[0] if tags else None

def check_lts_version(current_tag, recommended_tag, custom_rules, image_base):
    """Check if a version is valid according to LTS rules."""
    if not custom_rules or image_base not in custom_rules or "lts_versions" not in custom_rules[image_base]:
        return True  # No custom rules, so version is valid
    
    # Get LTS versions
    lts_versions = custom_rules[image_base]["lts_versions"]
    
    # Extract major versions
    current_major = None
    if current_tag:
        match = re.search(r'^\D*(\d+)', current_tag)
        if match:
            current_major = int(match.group(1))
    
    recommended_major = None
    if recommended_tag:
        match = re.search(r'^\D*(\d+)', recommended_tag)
        if match:
            recommended_major = int(match.group(1))
    
    # Check if current version is LTS
    if current_major is not None and current_major not in lts_versions:
        # Current version is not LTS, no need to check further
        return True
    
    # Check if recommended version is LTS
    if recommended_major is not None and recommended_major in lts_versions:
        # Both versions are LTS, valid upgrade
        return True
    
    # Current is LTS, but recommended is not
    if current_major is not None and recommended_major is not None:
        print(f"Warning: Current version {current_major} is LTS but recommended version {recommended_major} is not LTS")
        # Find next LTS version
        next_lts = None
        for lts in sorted(lts_versions):
            if lts > current_major:
                next_lts = lts
                break
        
        if next_lts:
            print(f"Next LTS version would be {next_lts}")
            # If recommended is higher than next LTS, it's valid
            if recommended_major > next_lts:
                return True
        
        # Otherwise, invalid upgrade
        return False
    
    # Default to valid
    return True

def calculate_version_gap(current_tag, recommended_tag, version_level=1, custom_rules=None, image_base=None):
    """
    Calculate version gap between current and recommended tags.
    
    Args:
        current_tag: Current version tag
        recommended_tag: Recommended version tag
        version_level: Level of version to consider (1=major, 2=major.minor, 3=major.minor.patch)
        custom_rules: Custom rules for specific images
        image_base: Base image name (e.g., 'node', 'debian')
    
    Returns:
        tuple: (gap, missing_versions) or None if versions can't be compared
    """
    # Check for skip_versions rule
    if custom_rules and image_base in custom_rules and "skip_versions" in custom_rules[image_base]:
        skip_versions = custom_rules[image_base]["skip_versions"]
    else:
        skip_versions = []
    
    try:
        # Handle 'v' prefix in version tags
        current_version_str = current_tag[1:] if current_tag.startswith('v') else current_tag
        recommended_version_str = recommended_tag[1:] if recommended_tag.startswith('v') else recommended_tag
        
        # Remove any variant suffixes (like -debug, -arm64v8)
        current_version_str = re.sub(r'-.*$', '', current_version_str)
        recommended_version_str = re.sub(r'-.*$', '', recommended_version_str)
        
        # Extract version parts
        current_parts = re.findall(r'\d+', current_version_str)
        recommended_parts = re.findall(r'\d+', recommended_version_str)
        
        if not current_parts or not recommended_parts:
            return None
            
        # Ensure we have enough parts
        while len(current_parts) < 3:
            current_parts.append('0')
        while len(recommended_parts) < 3:
            recommended_parts.append('0')
        
        # Convert to integers
        current_parts = [int(p) for p in current_parts[:3]]
        recommended_parts = [int(p) for p in recommended_parts[:3]]
        
        # Get the prefix format from the recommended tag
        prefix = 'v' if recommended_tag.startswith('v') else ''
        
        # Compare version parts up to specified level
        for i in range(version_level):
            if i >= len(current_parts) or i >= len(recommended_parts):
                break
                
            if recommended_parts[i] > current_parts[i]:
                # Calculate gap at this level
                gap = recommended_parts[i] - current_parts[i]
                
                # Create appropriate format for missing versions based on level
                missing_versions = []
                if i == 0:  # Major version
                    # For 0.x.x versions, treat it specially
                    if current_parts[0] == 0 and recommended_parts[0] == 0:
                        for j in range(current_parts[1] + 1, recommended_parts[1] + 1):
                            version_str = f"{prefix}0.{j}"
                            if str(j) not in skip_versions:
                                missing_versions.append(version_str)
                    else:
                        for j in range(current_parts[0] + 1, recommended_parts[0] + 1):
                            version_str = f"{prefix}{j}"
                            if str(j) not in skip_versions:
                                missing_versions.append(version_str)
                elif i == 1:  # Minor version
                    for j in range(current_parts[1] + 1, recommended_parts[1] + 1):
                        version_str = f"{prefix}{current_parts[0]}.{j}"
                        if str(j) not in skip_versions:
                            missing_versions.append(version_str)
                else:  # Patch version
                    for j in range(current_parts[2] + 1, recommended_parts[2] + 1):
                        version_str = f"{prefix}{current_parts[0]}.{current_parts[1]}.{j}"
                        if str(j) not in skip_versions:
                            missing_versions.append(version_str)
                
                # Adjust gap count if versions are being skipped
                real_gap = len(missing_versions)
                
                # Special case for step-by-N rule (like Node.js LTS every 2 versions)
                if custom_rules and image_base in custom_rules and "step_by" in custom_rules[image_base]:
                    step_by = custom_rules[image_base]["step_by"]
                    
                    if i == 0:  # Only apply to major versions
                        # Calculate how many steps this would be with the step rule
                        steps = (recommended_parts[0] - current_parts[0]) / step_by
                        # If it's a whole number of steps, it's valid
                        if steps.is_integer():
                            print(f"Following step-by-{step_by} rule: {current_parts[0]} → {recommended_parts[0]} (valid)")
                            # Adjust the gap to be in terms of steps
                            real_gap = int(steps)
                        else:
                            print(f"Following step-by-{step_by} rule: {current_parts[0]} → {recommended_parts[0]} is {steps} steps (not valid)")
                            # Find the nearest valid step
                            valid_step = current_parts[0] + (int(steps) * step_by)
                            if valid_step < recommended_parts[0]:
                                print(f"Nearest valid step would be: {valid_step}")
                            real_gap = int(steps) if steps > 0 else 1
                
                return real_gap, missing_versions
            elif recommended_parts[i] < current_parts[i]:
                # Current is newer at this level
                return 0, []
        
        # If we got here and haven't returned yet, versions are equal at the specified level
        return 0, []
    except Exception as e:
        print(f"Error calculating version gap: {e}")
        return None

def analyze_image_tags(image_name, image_count, total_images, threshold, force_level=None, private_registries=None, custom_rules=None):
    """Analyze tags for a specific image and display information."""
    print(f"\n{'='*50}")
    print(f"Image {image_count} of {total_images}: {image_name}")
    print(f"{'='*50}")
    
    # Default status is 'UNKNOWN'
    status = {
        'image': image_name,
        'status': 'UNKNOWN',
        'gap': None,
        'recommended': None,
        'current': None,
        'message': "Status could not be determined"
    }
    
    # Check if the registry is supported
    is_supported, registry_name = is_supported_registry(image_name)
    if not is_supported:
        print(f"Warning: {registry_name} is not supported for tag checking.")
        print(f"Cannot check for updates of {image_name}")
        print("Only Docker Hub images are currently supported.")
        status['message'] = f"Registry {registry_name} not supported"
        return status
    
    print("Downloading tags...")
    tags, recommended_tag = get_image_tags(image_name, private_registries)
    
    if not tags:
        print("Tags not found or could not access repository.")
        status['message'] = "No tags found or repository not accessible"
        return status
    
    # Get public image name for display
    public_image = get_public_image_name(image_name, private_registries)
    parts = public_image.split(':')
    base_image = parts[0]
    current_tag = parts[1] if len(parts) > 1 else None
    
    if not current_tag:
        print(f"Warning: Image {image_name} has no explicit tag (using 'latest' by default)")
        print("Cannot reliably check version status without explicit tag")
        status['message'] = "No explicit tag specified (using 'latest')"
        status['status'] = 'WARNING'
        return status
    
    # Get base image name for rule lookup
    image_base = base_image.split('/')[-1]
    
    # Detect or use forced version level
    version_level = force_level if force_level else detect_version_level(tags, base_image, custom_rules)
    level_name = {1: "major", 2: "minor", 3: "patch"}[version_level]
    
    print(f"\nUsing {level_name} version level ({version_level}) for comparison")
    
    # Apply custom rules if available
    if custom_rules and image_base in custom_rules:
        rule = custom_rules[image_base]
        if "lts_versions" in rule:
            lts_versions = rule["lts_versions"]
            print(f"Applying LTS version rule for {image_base}: {', '.join(map(str, lts_versions))}")
        
        if "step_by" in rule:
            step_by = rule["step_by"]
            print(f"Applying step-by-{step_by} rule for {image_base}")
        
        if "skip_versions" in rule:
            skip_versions = rule["skip_versions"]
            print(f"Skipping versions: {', '.join(skip_versions)}")
    
    print(f"\nAvailable tags for '{base_image}':")
    # Show only tags that look like versions
    version_tags = [tag for tag in tags if is_valid_version_tag(tag)]
    if not version_tags:
        # If no version tags were found, show some regular tags
        display_tags = sorted(tags)[:10]
        print("No clear version tags found. Sample of available tags:")
    else:
        # Show a sample of version tags
        display_tags = sorted(version_tags)[:10]
        print("Sample of version tags:")
        
    for tag in display_tags:
        print(f"  - {tag}")
    
    remainder = len(tags) - len(display_tags)
    if remainder > 0:
        print(f"  ... and {remainder} more tags")
    
    if recommended_tag:
        # Check LTS rules if applicable
        is_valid_upgrade = True
        if custom_rules and image_base in custom_rules and "lts_versions" in custom_rules[image_base]:
            is_valid_upgrade = check_lts_version(current_tag, recommended_tag, custom_rules, image_base)
            if not is_valid_upgrade:
                print(f"Warning: Upgrade from {current_tag} to {recommended_tag} violates LTS policy")
        
        # Default status is UP-TO-DATE
        status['status'] = 'UP-TO-DATE'
        status['recommended'] = recommended_tag
        status['current'] = current_tag
        status['message'] = "Image is up-to-date"
        
        # Check if we need to show the clean version by removing variants
        clean_recommended = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', recommended_tag)
        recommended_display = clean_recommended.group(1) if clean_recommended else recommended_tag
        
        # For current tag display
        clean_current = None
        if current_tag:
            clean_current = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', current_tag)
        current_display = clean_current.group(1) if clean_current else current_tag
        
        print(f"\nNewest semantic version: {recommended_display}")
        if current_tag and current_tag != recommended_tag:
            print(f"Actual version: {current_display}")
            
            # Calculate and display version gap
            version_gap_info = calculate_version_gap(
                current_tag, recommended_tag, version_level, custom_rules, image_base
            )
            
            if version_gap_info:
                gap, missing_versions = version_gap_info
                status['gap'] = gap
                
                if gap > 0:
                    # Determine if outdated based on threshold
                    if gap >= threshold:
                        # If LTS rule is violated, add a warning to the message
                        if not is_valid_upgrade:
                            status['status'] = 'WARNING'
                            status['message'] = f"Image is {gap} {level_name} version(s) behind but violates LTS policy"
                        else:
                            status['status'] = 'OUTDATED'
                            status['message'] = f"Image is {gap} {level_name} version(s) behind"
                    else:
                        status['message'] = f"Image is {gap} {level_name} version(s) behind but within threshold ({threshold})"
                    
                    # Show message with appropriate version level terminology
                    print(f"You are {gap} {level_name} version{'s' if gap > 1 else ''} behind")
                    
                    if missing_versions:
                        print(f"Missing versions: {', '.join(map(str, missing_versions))}")
                    else:
                        print("No direct upgrade path available")
                    
                    # Print status in a format easy to grep
                    if status['status'] in ['OUTDATED', 'WARNING']:
                        print(f"\nSTATUS: {status['status']} - {status['message']}")
                    else:
                        print(f"\nSTATUS: {status['status']} - {status['message']}")
                else:
                    print(f"You are using the latest {level_name} version")
    else:
        status['message'] = "Could not determine newest version"
    
    return status

def parse_private_registries(args):
    """Parse private registry arguments from command line."""
    private_registries = []
    
    # Check for --private-registry flag
    if "--private-registry" in args:
        # Find the index where the flag is
        try:
            idx = args.index("--private-registry")
            
            # Check if there's a value after the flag
            if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                # Single registry specified
                private_registries.append(args[idx + 1])
            else:
                # No value provided, use default
                private_registries.append("docker-registry.gitlab:4567")
        except ValueError:
            pass
    
    # Check for --private-registries-file flag
    if "--private-registries-file" in args:
        try:
            idx = args.index("--private-registries-file")
            if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                file_path = args[idx + 1]
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            registry = line.strip()
                            if registry and not registry.startswith('#'):
                                private_registries.append(registry)
                except Exception as e:
                    print(f"Error reading private registries file: {e}")
        except ValueError:
            pass
    
    return private_registries

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 dockerfile_parser.py <path_to_Dockerfile> [options]")
        print("Options:")
        print("  --tags: Show available tags for images")
        print("  --threshold N: Set the version gap threshold for marking images as outdated (default: 3)")
        print("  --level N: Force specific version level for comparison (1=major, 2=minor, 3=patch)")
        print("  --private-registry [REGISTRY]: Mark images from specified private registry")
        print("  --private-registries-file FILE: File containing list of private registries")
        print("  --rules FILE: JSON file with custom rules for specific images")
        print
        #!/usr/bin/env python3
import re
import sys
import os.path
import json
import urllib.request
from packaging import version
from collections import defaultdict

def extract_base_images(dockerfile_path):
    """Extracts all base images from a Dockerfile, including multiple FROM instructions."""
    try:
        if not os.path.isfile(dockerfile_path):
            print(f"Error: File {dockerfile_path} not found.")
            return []
            
        with open(dockerfile_path, 'r') as dockerfile:
            content = dockerfile.read()
            pattern = r'^\s*FROM\s+(--platform=[^\s]+\s+)?([^\s]+)(\s+AS\s+[^\s]+)?'
            
            images = []
            for line in content.split('\n'):
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    image_name = match.group(2)
                    stage_name = match.group(3).strip() if match.group(3) else None
                    images.append({
                        'image': image_name,
                        'stage': stage_name
                    })
            
            if not images:
                print("FROM instruction not found in Dockerfile")
                return []
            
            return images
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

def get_public_image_name(image_name, private_registries=None):
    """
    Extract public image name from a private registry image name.
    
    Args:
        image_name: Full image name
        private_registries: List of private registry prefixes to check
    
    Returns:
        str: Public image name without registry prefix if applicable
    """
    if not private_registries:
        return image_name
    
    for registry in private_registries:
        if registry in image_name:
            # Remove registry prefix
            parts = image_name.split('/')
            # Find the index where the registry prefix ends
            registry_parts = registry.split('/')
            registry_base = registry_parts[0]  # Get the domain part
            
            for i, part in enumerate(parts):
                if registry_base in part:
                    # Remove all parts up to and including this one
                    public_image = '/'.join(parts[i+1:])
                    print(f"Removing private registry prefix '{registry}', using: {public_image}")
                    return public_image
    
    return image_name

def is_supported_registry(image_name):
    """Check if the image is from a supported registry."""
    unsupported_registries = [
        "gcr.io",
        "k8s.gcr.io",
        "asia.gcr.io",
        "eu.gcr.io",
        "us.gcr.io",
        "ghcr.io",
        "quay.io",
        "ecr.aws"
    ]
    
    for registry in unsupported_registries:
        if registry in image_name:
            return False, registry
    
    return True, None

def get_image_tags(image_name, private_registries=None):
    """Fetches tags for an image and finds the best available version."""
    # Check if the registry is supported
    is_supported, registry_name = is_supported_registry(image_name)
    if not is_supported:
        print(f"Warning: {registry_name} is not supported for tag checking.")
        print(f"Cannot check for updates of {image_name}")
        print("Only Docker Hub images are currently supported.")
        return [], None
        
    # Get public image name regardless of whether it's from a private registry
    public_image = get_public_image_name(image_name, private_registries)
    # Split image and tag
    parts = public_image.split(':')
    image = parts[0]
    current_tag = parts[1] if len(parts) > 1 else None
    
    # Prepare for Docker Hub API
    if '/' not in image:
        image = f"library/{image}"
    
    try:
        url = f"https://hub.docker.com/v2/repositories/{image}/tags?page_size=100"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            tags = [tag['name'] for tag in data.get('results', [])]
            
            recommended_tag = find_recommended_tag(tags, current_tag)
            
            return tags, recommended_tag
    except Exception as e:
        print(f"Error during fetching tags: {str(e)}")
        return [], None

def is_valid_version_tag(tag):
    """Check if a tag looks like a valid semantic version and not a date or other numeric ID."""
    # Skip tags that are just long numbers (like dates: 20220101)
    if re.match(r'^\d{6,}$', tag):
        return False
        
    # Skip tags with too many numeric segments (probably not a version)
    if len(re.findall(r'\d+', tag)) > 4:
        return False
    
    # Skip tags with too many digits in total (probably a date or ID)
    total_digits = sum(len(digit) for digit in re.findall(r'\d+', tag))
    if total_digits > 8:
        return False
    
    # Acceptable patterns for versions
    # Examples: 3.19, v2.1.0, 1.24-alpine
    return re.match(r'^v?\d+(\.\d+){0,3}(-[a-z0-9]+)?$', tag) is not None

def load_custom_rules(rules_file):
    """Load custom rules from a JSON file."""
    if not os.path.isfile(rules_file):
        print(f"Warning: Rules file {rules_file} not found.")
        return {}
    
    try:
        with open(rules_file, 'r') as f:
            rules = json.load(f)
            print(f"Loaded custom rules for {len(rules)} images")
            return rules
    except Exception as e:
        print(f"Error loading rules file: {e}")
        return {}

def detect_version_level(tags, base_image_name, custom_rules=None):
    """
    Automatically detect the significant version level for an image by analyzing its tags.
    Uses custom rules if provided.
    
    Returns:
        int: The significant version level (1, 2, or 3)
    """
    # Default to level 1 (major version only)
    default_level = 1
    
    # Special handling for known images
    image_base = base_image_name.split('/')[-1]  # Get last part of image name (e.g., 'debian' from 'library/debian')
    
    # Check custom rules first if provided
    if custom_rules and image_base in custom_rules:
        rule = custom_rules[image_base]
        if "level" in rule:
            print(f"Using custom version level for {image_base}: {rule['level']}")
            return rule["level"]
    
    # Special cases based on image name
    special_cases = {
        'debian': 1,       # Debian uses x.y where x is the major release
        'ubuntu': 1,       # Ubuntu uses YY.MM format
        'centos': 1,       # CentOS uses single digit versions
        'alpine': 2,       # Alpine has frequent minor version updates (3.18, 3.19, etc.)
        'nginx': 2,        # nginx stays on 1.x for a long time
        'node': 1,         # Node.js has meaningful major versions (14, 16, 18, etc.)
        'python': 2,       # Python has meaningful minor versions (3.9, 3.10, etc.)
        'php': 2,          # PHP has meaningful minor versions (8.0, 8.1, etc.)
        'golang': 2,       # Go has meaningful minor versions (1.18, 1.19, etc.)
        'postgres': 2,     # PostgreSQL has meaningful minor versions (14.1, 14.2, etc.)
        'mysql': 1,        # MySQL major versions are significant (5.x, 8.x)
        'mariadb': 2,      # MariaDB has meaningful minor versions (10.5, 10.6, etc.)
        'mongo': 2,        # MongoDB has meaningful minor versions (4.4, 5.0, etc.)
        'redis': 2,        # Redis has meaningful minor versions (6.2, 7.0, etc.)
    }
    
    if image_base in special_cases:
        return special_cases[image_base]
    
    # Filter to just version tags
    version_tags = [tag for tag in tags if is_valid_version_tag(tag)]
    if not version_tags:
        return default_level
    
    # Analyze version patterns to detect significant level
    pattern_counts = defaultdict(int)
    
    for tag in version_tags:
        # Remove v prefix if present
        clean_tag = tag[1:] if tag.startswith('v') else tag
        
        # Remove suffix (like -alpine)
        clean_tag = re.sub(r'-.*$', '', clean_tag)
        
        # Count dots to determine version pattern
        parts = clean_tag.split('.')
        pattern = len(parts)
        pattern_counts[pattern] += 1
    
    # Check version difference patterns
    if len(version_tags) > 1:
        try:
            # Parse versions
            parsed_versions = []
            for tag in version_tags:
                clean_tag = tag[1:] if tag.startswith('v') else tag
                clean_tag = re.sub(r'-.*$', '', clean_tag)
                try:
                    v = version.parse(clean_tag)
                    parsed_versions.append((v, clean_tag))
                except:
                    pass
            
            if parsed_versions:
                # Sort by version
                sorted_versions = sorted(parsed_versions, key=lambda x: x[0])
                
                # Analyze version changes
                level_changes = defaultdict(int)
                
                for i in range(1, len(sorted_versions)):
                    prev_parts = sorted_versions[i-1][1].split('.')
                    curr_parts = sorted_versions[i][1].split('.')
                    
                    # Ensure we have at least 3 parts for comparison
                    while len(prev_parts) < 3:
                        prev_parts.append('0')
                    while len(curr_parts) < 3:
                        curr_parts.append('0')
                    
                    # Check which parts changed
                    for j in range(min(3, len(prev_parts))):
                        if prev_parts[j] != curr_parts[j]:
                            level_changes[j+1] += 1
                            break
                
                # Determine most common change level
                if level_changes:
                    most_common_level = max(level_changes.items(), key=lambda x: x[1])[0]
                    return most_common_level
        except Exception as e:
            print(f"Error in version pattern analysis: {e}")
    
    # If we can't determine a pattern, use most common format
    if pattern_counts:
        most_common_pattern = max(pattern_counts.items(), key=lambda x: x[1])[0]
        if most_common_pattern == 1:
            return 1  # Just major version
        elif most_common_pattern == 2:
            return 2  # Major.minor
        else:
            return 2  # Default to 2 levels for 3+ part versions
    
    return default_level

def find_recommended_tag(tags, current_tag=None):
    """Finds the newest numeric version from available tags."""
    if not tags:
        return None
    
    # For tags with 'v' prefix, separate the base versions from variants
    clean_tags = {}
    
    for tag in tags:
        # Skip development/test versions
        if any(x in tag for x in ['alpha', 'beta', 'rc', 'dev', 'test']):
            continue
            
        # Try to match the pattern for versioned tags
        match = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', tag)
        if match:
            # Extract the base version (without variants like -debug, -arm64v8)
            base_version = match.group(1)
            
            # Additional validation for version tags
            if not is_valid_version_tag(base_version):
                continue
                
            # Save the original tag for later retrieval
            if base_version not in clean_tags:
                clean_tags[base_version] = tag
    
    # Process the clean base versions to find the newest
    numeric_versions = []
    for base_version in clean_tags.keys():
        try:
            # Remove 'v' prefix for version comparison if present
            version_str = base_version[1:] if base_version.startswith('v') else base_version
            v = version.parse(version_str)
            numeric_versions.append((v, clean_tags[base_version]))
        except:
            pass
    
    # Return the tag with the newest version
    if numeric_versions:
        return sorted(numeric_versions, key=lambda x: x[0])[-1][1]
    
    # Fallbacks if no clean numeric versions found
    if 'stable' in tags:
        return 'stable'
    
    for tag in tags:
        if tag != 'latest':
            return tag
    
    return tags[0] if tags else None

def check_lts_version(current_tag, recommended_tag, custom_rules, image_base):
    """Check if a version is valid according to LTS rules."""
    if not custom_rules or image_base not in custom_rules or "lts_versions" not in custom_rules[image_base]:
        return True  # No custom rules, so version is valid
    
    # Get LTS versions
    lts_versions = custom_rules[image_base]["lts_versions"]
    
    # Extract major versions
    current_major = None
    if current_tag:
        match = re.search(r'^\D*(\d+)', current_tag)
        if match:
            current_major = int(match.group(1))
    
    recommended_major = None
    if recommended_tag:
        match = re.search(r'^\D*(\d+)', recommended_tag)
        if match:
            recommended_major = int(match.group(1))
    
    # Check if current version is LTS
    if current_major is not None and current_major not in lts_versions:
        # Current version is not LTS, no need to check further
        return True
    
    # Check if recommended version is LTS
    if recommended_major is not None and recommended_major in lts_versions:
        # Both versions are LTS, valid upgrade
        return True
    
    # Current is LTS, but recommended is not
    if current_major is not None and recommended_major is not None:
        print(f"Warning: Current version {current_major} is LTS but recommended version {recommended_major} is not LTS")
        # Find next LTS version
        next_lts = None
        for lts in sorted(lts_versions):
            if lts > current_major:
                next_lts = lts
                break
        
        if next_lts:
            print(f"Next LTS version would be {next_lts}")
            # If recommended is higher than next LTS, it's valid
            if recommended_major > next_lts:
                return True
        
        # Otherwise, invalid upgrade
        return False
    
    # Default to valid
    return True

def calculate_version_gap(current_tag, recommended_tag, version_level=1, custom_rules=None, image_base=None):
    """
    Calculate version gap between current and recommended tags.
    
    Args:
        current_tag: Current version tag
        recommended_tag: Recommended version tag
        version_level: Level of version to consider (1=major, 2=major.minor, 3=major.minor.patch)
        custom_rules: Custom rules for specific images
        image_base: Base image name (e.g., 'node', 'debian')
    
    Returns:
        tuple: (gap, missing_versions) or None if versions can't be compared
    """
    # Check for skip_versions rule
    if custom_rules and image_base in custom_rules and "skip_versions" in custom_rules[image_base]:
        skip_versions = custom_rules[image_base]["skip_versions"]
    else:
        skip_versions = []
    
    try:
        # Handle 'v' prefix in version tags
        current_version_str = current_tag[1:] if current_tag.startswith('v') else current_tag
        recommended_version_str = recommended_tag[1:] if recommended_tag.startswith('v') else recommended_tag
        
        # Remove any variant suffixes (like -debug, -arm64v8)
        current_version_str = re.sub(r'-.*$', '', current_version_str)
        recommended_version_str = re.sub(r'-.*$', '', recommended_version_str)
        
        # Extract version parts
        current_parts = re.findall(r'\d+', current_version_str)
        recommended_parts = re.findall(r'\d+', recommended_version_str)
        
        if not current_parts or not recommended_parts:
            return None
            
        # Ensure we have enough parts
        while len(current_parts) < 3:
            current_parts.append('0')
        while len(recommended_parts) < 3:
            recommended_parts.append('0')
        
        # Convert to integers
        current_parts = [int(p) for p in current_parts[:3]]
        recommended_parts = [int(p) for p in recommended_parts[:3]]
        
        # Get the prefix format from the recommended tag
        prefix = 'v' if recommended_tag.startswith('v') else ''
        
        # Compare version parts up to specified level
        for i in range(version_level):
            if i >= len(current_parts) or i >= len(recommended_parts):
                break
                
            if recommended_parts[i] > current_parts[i]:
                # Calculate gap at this level
                gap = recommended_parts[i] - current_parts[i]
                
                # Create appropriate format for missing versions based on level
                missing_versions = []
                if i == 0:  # Major version
                    # For 0.x.x versions, treat it specially
                    if current_parts[0] == 0 and recommended_parts[0] == 0:
                        for j in range(current_parts[1] + 1, recommended_parts[1] + 1):
                            version_str = f"{prefix}0.{j}"
                            if str(j) not in skip_versions:
                                missing_versions.append(version_str)
                    else:
                        for j in range(current_parts[0] + 1, recommended_parts[0] + 1):
                            version_str = f"{prefix}{j}"
                            if str(j) not in skip_versions:
                                missing_versions.append(version_str)
                elif i == 1:  # Minor version
                    for j in range(current_parts[1] + 1, recommended_parts[1] + 1):
                        version_str = f"{prefix}{current_parts[0]}.{j}"
                        if str(j) not in skip_versions:
                            missing_versions.append(version_str)
                else:  # Patch version
                    for j in range(current_parts[2] + 1, recommended_parts[2] + 1):
                        version_str = f"{prefix}{current_parts[0]}.{current_parts[1]}.{j}"
                        if str(j) not in skip_versions:
                            missing_versions.append(version_str)
                
                # Adjust gap count if versions are being skipped
                real_gap = len(missing_versions)
                
                # Special case for step-by-N rule (like Node.js LTS every 2 versions)
                if custom_rules and image_base in custom_rules and "step_by" in custom_rules[image_base]:
                    step_by = custom_rules[image_base]["step_by"]
                    
                    if i == 0:  # Only apply to major versions
                        # Calculate how many steps this would be with the step rule
                        steps = (recommended_parts[0] - current_parts[0]) / step_by
                        # If it's a whole number of steps, it's valid
                        if steps.is_integer():
                            print(f"Following step-by-{step_by} rule: {current_parts[0]} → {recommended_parts[0]} (valid)")
                            # Adjust the gap to be in terms of steps
                            real_gap = int(steps)
                        else:
                            print(f"Following step-by-{step_by} rule: {current_parts[0]} → {recommended_parts[0]} is {steps} steps (not valid)")
                            # Find the nearest valid step
                            valid_step = current_parts[0] + (int(steps) * step_by)
                            if valid_step < recommended_parts[0]:
                                print(f"Nearest valid step would be: {valid_step}")
                            real_gap = int(steps) if steps > 0 else 1
                
                return real_gap, missing_versions
            elif recommended_parts[i] < current_parts[i]:
                # Current is newer at this level
                return 0, []
        
        # If we got here and haven't returned yet, versions are equal at the specified level
        return 0, []
    except Exception as e:
        print(f"Error calculating version gap: {e}")
        return None

def analyze_image_tags(image_name, image_count, total_images, threshold, force_level=None, private_registries=None, custom_rules=None):
    """Analyze tags for a specific image and display information."""
    print(f"\n{'='*50}")
    print(f"Image {image_count} of {total_images}: {image_name}")
    print(f"{'='*50}")
    
    # Default status is 'UNKNOWN'
    status = {
        'image': image_name,
        'status': 'UNKNOWN',
        'gap': None,
        'recommended': None,
        'current': None,
        'message': "Status could not be determined"
    }
    
    # Check if the registry is supported
    is_supported, registry_name = is_supported_registry(image_name)
    if not is_supported:
        print(f"Warning: {registry_name} is not supported for tag checking.")
        print(f"Cannot check for updates of {image_name}")
        print("Only Docker Hub images are currently supported.")
        status['message'] = f"Registry {registry_name} not supported"
        return status
    
    print("Downloading tags...")
    tags, recommended_tag = get_image_tags(image_name, private_registries)
    
    if not tags:
        print("Tags not found or could not access repository.")
        status['message'] = "No tags found or repository not accessible"
        return status
    
    # Get public image name for display
    public_image = get_public_image_name(image_name, private_registries)
    parts = public_image.split(':')
    base_image = parts[0]
    current_tag = parts[1] if len(parts) > 1 else None
    
    if not current_tag:
        print(f"Warning: Image {image_name} has no explicit tag (using 'latest' by default)")
        print("Cannot reliably check version status without explicit tag")
        status['message'] = "No explicit tag specified (using 'latest')"
        status['status'] = 'WARNING'
        return status
    
    # Get base image name for rule lookup
    image_base = base_image.split('/')[-1]
    
    # Detect or use forced version level
    version_level = force_level if force_level else detect_version_level(tags, base_image, custom_rules)
    level_name = {1: "major", 2: "minor", 3: "patch"}[version_level]
    
    print(f"\nUsing {level_name} version level ({version_level}) for comparison")
    
    # Apply custom rules if available
    if custom_rules and image_base in custom_rules:
        rule = custom_rules[image_base]
        if "lts_versions" in rule:
            lts_versions = rule["lts_versions"]
            print(f"Applying LTS version rule for {image_base}: {', '.join(map(str, lts_versions))}")
        
        if "step_by" in rule:
            step_by = rule["step_by"]
            print(f"Applying step-by-{step_by} rule for {image_base}")
        
        if "skip_versions" in rule:
            skip_versions = rule["skip_versions"]
            print(f"Skipping versions: {', '.join(skip_versions)}")
    
    print(f"\nAvailable tags for '{base_image}':")
    # Show only tags that look like versions
    version_tags = [tag for tag in tags if is_valid_version_tag(tag)]
    if not version_tags:
        # If no version tags were found, show some regular tags
        display_tags = sorted(tags)[:10]
        print("No clear version tags found. Sample of available tags:")
    else:
        # Show a sample of version tags
        display_tags = sorted(version_tags)[:10]
        print("Sample of version tags:")
        
    for tag in display_tags:
        print(f"  - {tag}")
    
    remainder = len(tags) - len(display_tags)
    if remainder > 0:
        print(f"  ... and {remainder} more tags")
    
    if recommended_tag:
        # Check LTS rules if applicable
        is_valid_upgrade = True
        if custom_rules and image_base in custom_rules and "lts_versions" in custom_rules[image_base]:
            is_valid_upgrade = check_lts_version(current_tag, recommended_tag, custom_rules, image_base)
            if not is_valid_upgrade:
                print(f"Warning: Upgrade from {current_tag} to {recommended_tag} violates LTS policy")
        
        # Default status is UP-TO-DATE
        status['status'] = 'UP-TO-DATE'
        status['recommended'] = recommended_tag
        status['current'] = current_tag
        status['message'] = "Image is up-to-date"
        
        # Check if we need to show the clean version by removing variants
        clean_recommended = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', recommended_tag)
        recommended_display = clean_recommended.group(1) if clean_recommended else recommended_tag
        
        # For current tag display
        clean_current = None
        if current_tag:
            clean_current = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', current_tag)
        current_display = clean_current.group(1) if clean_current else current_tag
        
        print(f"\nNewest semantic version: {recommended_display}")
        if current_tag and current_tag != recommended_tag:
            print(f"Actual version: {current_display}")
            
            # Calculate and display version gap
            version_gap_info = calculate_version_gap(
                current_tag, recommended_tag, version_level, custom_rules, image_base
            )
            
            if version_gap_info:
                gap, missing_versions = version_gap_info
                status['gap'] = gap
                
                if gap > 0:
                    # Determine if outdated based on threshold
                    if gap >= threshold:
                        # If LTS rule is violated, add a warning to the message
                        if not is_valid_upgrade:
                            status['status'] = 'WARNING'
                            status['message'] = f"Image is {gap} {level_name} version(s) behind but violates LTS policy"
                        else:
                            status['status'] = 'OUTDATED'
                            status['message'] = f"Image is {gap} {level_name} version(s) behind"
                    else:
                        status['message'] = f"Image is {gap} {level_name} version(s) behind but within threshold ({threshold})"
                    
                    # Show message with appropriate version level terminology
                    print(f"You are {gap} {level_name} version{'s' if gap > 1 else ''} behind")
                    
                    if missing_versions:
                        print(f"Missing versions: {', '.join(map(str, missing_versions))}")
                    else:
                        print("No direct upgrade path available")
                    
                    # Print status in a format easy to grep
                    if status['status'] in ['OUTDATED', 'WARNING']:
                        print(f"\nSTATUS: {status['status']} - {status['message']}")
                    else:
                        print(f"\nSTATUS: {status['status']} - {status['message']}")
                else:
                    print(f"You are using the latest {level_name} version")
    else:
        status['message'] = "Could not determine newest version"
    
    return status

def parse_private_registries(args):
    """Parse private registry arguments from command line."""
    private_registries = []
    
    # Check for --private-registry flag
    if "--private-registry" in args:
        # Find the index where the flag is
        try:
            idx = args.index("--private-registry")
            
            # Check if there's a value after the flag
            if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                # Single registry specified
                private_registries.append(args[idx + 1])
            else:
                # No value provided, use default
                private_registries.append("docker-registry.gitlab.co:4567")
        except ValueError:
            pass
    
    # Check for --private-registries-file flag
    if "--private-registries-file" in args:
        try:
            idx = args.index("--private-registries-file")
            if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                file_path = args[idx + 1]
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            registry = line.strip()
                            if registry and not registry.startswith('#'):
                                private_registries.append(registry)
                except Exception as e:
                    print(f"Error reading private registries file: {e}")
        except ValueError:
            pass
    
    return private_registries

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 dockerfile_parser.py <path_to_Dockerfile> [options]")
        print("Options:")
        print("  --tags: Show available tags for images")
        print("  --threshold N: Set the version gap threshold for marking images as outdated (default: 3)")
        print("  --level N: Force specific version level for comparison (1=major, 2=minor, 3=patch)")
        print("  --private-registry [REGISTRY]: Mark images from specified private registry")
        print("  --private-registries-file FILE: File containing list of private registries")
        print("  --rules FILE: JSON file with custom rules for specific images")
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
    
    image_info_list = extract_base_images(dockerfile_path)
    
    if not image_info_list:
        print("No valid images found in Dockerfile.")
        sys.exit(1)
    
    print(f"Found {len(image_info_list)} image{'s' if len(image_info_list) > 1 else ''} in Dockerfile:")
    for i, info in enumerate(image_info_list, 1):
        stage_info = f" (stage: {info['stage']})" if info['stage'] else ""
        print(f"{i}. {info['image']}{stage_info}")
    
    outdated_images = []
    warning_images = []
    unknown_images = []
    
    if show_tags:
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
            
            if status['status'] == 'OUTDATED':
                outdated_images.append(status)
            elif status['status'] == 'WARNING':
                warning_images.append(status)
            elif status['status'] == 'UNKNOWN':
                unknown_images.append(status)
    
    # Print summary
    print("\n" + "="*50)
    print("DOCKERFILE ANALYSIS SUMMARY")
    print("="*50)
    
    if outdated_images:
        print(f"\n⛔ {len(outdated_images)} OUTDATED IMAGE(S):")
        for img in outdated_images:
            print(f"  - {img['image']} : {img['message']}")
    
    if warning_images:
        print(f"\n⚠️ {len(warning_images)} WARNING(S):")
        for img in warning_images:
            print(f"  - {img['image']} : {img['message']}")
    
    if unknown_images:
        print(f"\n❓ {len(unknown_images)} UNKNOWN STATUS:")
        for img in unknown_images:
            print(f"  - {img['image']} : {img['message']}")
    
    if not outdated_images and not warning_images and not unknown_images:
        print("\n✅ ALL IMAGES UP-TO-DATE")
        sys.exit(0)
    elif outdated_images:
        print("\n⛔ RESULT: OUTDATED - At least one image is outdated beyond threshold")
        sys.exit(1)
    else:
        print("\n⚠️ RESULT: WARNING - Some images have warnings or unknown status")
        sys.exit(0)

if __name__ == "__main__":
    main()