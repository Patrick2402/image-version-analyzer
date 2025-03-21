import re
from utils.registry_utils import get_image_tags, is_supported_registry, get_public_image_name, is_valid_version_tag
from utils.version_utils import detect_version_level, calculate_version_gap, check_lts_version

def analyze_image_tags(image_name, image_count, total_images, threshold, force_level=None, private_registries=None, custom_rules=None, no_info=False):
    """Analyze tags for a specific image and display information."""
    if not no_info:
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
        if not no_info:
            print(f"Warning: {registry_name} is not supported for tag checking.")
            print(f"Cannot check for updates of {image_name}")
            print("Only Docker Hub images are currently supported.")
        status['message'] = f"Registry {registry_name} not supported"
        return status
    
    if not no_info:
        print("Downloading tags...")
    tags, recommended_tag = get_image_tags(image_name, private_registries)
    if not tags:
        if not no_info:
            print("Tags not found or could not access repository.")
        status['message'] = "No tags found or repository not accessible"
        return status
    
    # Get public image name for display
    public_image = get_public_image_name(image_name, private_registries)
    parts = public_image.split(':')
    base_image = parts[0]
    current_tag = parts[1] if len(parts) > 1 else None
    
    if not current_tag:
        if not no_info:
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
    
    if not no_info:
        print(f"\nUsing {level_name} version level ({version_level}) for comparison")
    
    # Apply custom rules if available
    if custom_rules and image_base in custom_rules:
        rule = custom_rules[image_base]
        if not no_info:
            if "lts_versions" in rule:
                lts_versions = rule["lts_versions"]
                print(f"Applying LTS version rule for {image_base}: {', '.join(map(str, lts_versions))}")
            
            if "step_by" in rule:
                step_by = rule["step_by"]
                print(f"Applying step-by-{step_by} rule for {image_base}")
            
            if "skip_versions" in rule:
                skip_versions = rule["skip_versions"]
                print(f"Skipping versions: {', '.join(skip_versions)}")
    
    if not no_info:
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
            if not is_valid_upgrade and not no_info:
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
        
        if not no_info:
            print(f"\nNewest semantic version: {recommended_display}")
        if current_tag and current_tag != recommended_tag:
            if not no_info:
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
                    if not no_info:
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
                    if not no_info:
                        print(f"You are using the latest {level_name} version")
    else:
        status['message'] = "Could not determine newest version"
    
    return status