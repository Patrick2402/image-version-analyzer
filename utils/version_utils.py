import re
from packaging import version
from collections import defaultdict

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
    
    from registry_utils import is_valid_version_tag
    
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