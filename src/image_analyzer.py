import re
from utils.registry_utils import get_image_tags, is_supported_registry, get_public_image_name, is_valid_version_tag
from utils.version_utils import detect_version_level, calculate_version_gap, check_lts_version

def analyze_image_tags(image_name, image_count, total_images, threshold, force_level=None, private_registries=None, custom_rules=None, no_info=False):
    """Analyze tags for a specific image and display information in a simplified format."""
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
            print(f"! {registry_name} registry not supported for {image_name}")
        status['message'] = f"Registry {registry_name} not supported"
        return status
    
    if not no_info:
        pass
    
    tags, recommended_tag = get_image_tags(image_name, private_registries)
    if not tags:
        if not no_info:
            print("! No tags found or repository not accessible")
        status['message'] = "No tags found or repository not accessible"
        return status
    
    # Get public image name for display
    public_image = get_public_image_name(image_name, private_registries)
    parts = public_image.split(':')
    base_image = parts[0]
    current_tag = parts[1] if len(parts) > 1 else None
    
    if not current_tag:
        if not no_info:
            print(f"! Warning: No explicit tag specified (using 'latest')")
        status['message'] = "No explicit tag specified (using 'latest')"
        status['status'] = 'WARNING'
        return status
    
    # Get base image name for rule lookup
    image_base = base_image.split('/')[-1]
    
    # Detect or use forced version level
    version_level = force_level if force_level else detect_version_level(tags, base_image, custom_rules)
    level_name = {1: "major", 2: "minor", 3: "patch"}[version_level]
    
    # Show tag info if requested
    if not no_info and recommended_tag:
        # For verbose mode, show tag information
        # Extract variants from current and recommended tags
        current_variant = None
        recommended_variant = None
        
        # Detect variants
        current_variant_match = re.match(r'^v?\d+(\.\d+)*-(.+)$', current_tag)
        if current_variant_match:
            current_variant = current_variant_match.group(2)
            
        recommended_variant_match = re.match(r'^v?\d+(\.\d+)*-(.+)$', recommended_tag)
        if recommended_variant_match:
            recommended_variant = recommended_variant_match.group(2)
            
        if current_variant and recommended_variant and current_variant == recommended_variant:
            print(f"• Maintained variant: {current_variant}")
    
    if recommended_tag:
        # Check LTS rules if applicable
        is_valid_upgrade = True
        if custom_rules and image_base in custom_rules and "lts_versions" in custom_rules[image_base]:
            is_valid_upgrade = check_lts_version(current_tag, recommended_tag, custom_rules, image_base)
            if not is_valid_upgrade and not no_info:
                print(f"! LTS policy violation: {current_tag} → {recommended_tag}")
        
        # Default status is UP-TO-DATE
        status['status'] = 'UP-TO-DATE'
        status['recommended'] = recommended_tag
        status['current'] = current_tag
        status['message'] = "Image is up-to-date"
        
        # Get clean version numbers for display
        clean_recommended = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', recommended_tag)
        recommended_display = clean_recommended.group(1) if clean_recommended else recommended_tag
        
        clean_current = None
        if current_tag:
            clean_current = re.match(r'^(v?\d+(\.\d+)*)(-.*)?$', current_tag)
        current_display = clean_current.group(1) if clean_current else current_tag
        
        # Only show available tags if requested and not in quiet mode
        if not no_info:
            # Show tag info
            print(f"• Current: {current_tag} | Latest: {recommended_tag}")
            
            # If in verbose mode (--tags), show sample of available tags
            if not no_info:
                version_tags = [tag for tag in tags if is_valid_version_tag(tag)]
                if version_tags:
                    pass
        
        # If current tag is different from recommended
        if current_tag and current_tag != recommended_tag:
            # Calculate version gap
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
                    
                    # Show gap info in a simplified way
                    if not no_info:
                        if missing_versions:
                            print(f"• {gap} version(s) behind: {', '.join(missing_versions[:3])}" + 
                                  (f" + {len(missing_versions)-3} more" if len(missing_versions) > 3 else ""))
                    
                    # Show final status
                    if not no_info and status['status'] in ['OUTDATED', 'WARNING']:
                        if status['status'] == 'OUTDATED':
                            print(f"✘ OUTDATED: {current_display} → {recommended_display} ({gap} {level_name} versions)")
                        else:
                            print(f"⚠ WARNING: {current_display} → {recommended_display} (LTS policy violation)")
                else:
                    if not no_info:
                        print(f"✓ UP-TO-DATE: Using latest {level_name} version")
            else:
                if not no_info:
                    print("! Could not calculate version gap")
        else:
            # Current tag is the same as recommended
            if not no_info:
                print(f"✓ UP-TO-DATE: Using latest version")
    else:
        status['message'] = "Could not determine newest version"
        if not no_info:
            print("! Could not determine newest version")
    
    return status