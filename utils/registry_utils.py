import json
import urllib.request
import re

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
        # First try a larger page size to get more tags at once
        url = f"https://hub.docker.com/v2/repositories/{image}/tags?page_size=100"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            tags = [tag['name'] for tag in data.get('results', [])]
            
            # If there are more tags and we're looking for a variant, fetch more pages
            next_url = data.get('next')
            if next_url and current_tag and '-' in current_tag:
                # Extract the variant
                variant_match = re.match(r'^v?\d+(\.\d+)*-(.+)$', current_tag)
                if variant_match:
                    variant = variant_match.group(2)
                    # Fetch up to 5 more pages to find matching variants
                    page_count = 1
                    while next_url and page_count < 5:
                        try:
                            with urllib.request.urlopen(next_url) as next_response:
                                next_data = json.loads(next_response.read().decode('utf-8'))
                                next_tags = [tag['name'] for tag in next_data.get('results', [])]
                                tags.extend(next_tags)
                                next_url = next_data.get('next')
                                page_count += 1
                                
                                # If we found a tag with our variant and the newest version, stop fetching
                                # This is an optimization to avoid fetching all pages
                                newest_version_found = False
                                for tag in next_tags:
                                    if f"-{variant}" in tag and any(digit in tag for digit in ["1.24", "1.23"]):  # For golang
                                        newest_version_found = True
                                        break
                                if newest_version_found:
                                    break
                        except Exception as e:
                            print(f"Error fetching additional tags page: {e}")
                            break
            
            # Pass the current tag to find_recommended_tag
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

def find_recommended_tag(tags, current_tag=None):
    """Finds the newest numeric version from available tags with preference for matching variant."""
    if not tags:
        return None
    
    # Extract variant from current tag if it exists
    current_variant = None
    if current_tag:
        variant_match = re.match(r'^v?\d+(\.\d+)*-(.+)$', current_tag)
        if variant_match:
            current_variant = variant_match.group(2)
            print(f"Current tag variant: {current_variant}")
    
    # For tags with 'v' prefix, separate the base versions from variants
    base_versions = {}  # Map from base version to list of tags
    
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
                
            # Save all tags for this base version
            if base_version not in base_versions:
                base_versions[base_version] = []
            base_versions[base_version].append(tag)
    
    # Process the base versions to find the newest
    numeric_versions = []
    for base_version, version_tags in base_versions.items():
        try:
            # Remove 'v' prefix for version comparison if present
            from packaging import version
            version_str = base_version[1:] if base_version.startswith('v') else base_version
            v = version.parse(version_str)
            numeric_versions.append((v, base_version, version_tags))
        except Exception as e:
            print(f"Error parsing version {base_version}: {e}")
    
    if not numeric_versions:
        return None
    
    # Sort by version
    sorted_versions = sorted(numeric_versions, key=lambda x: x[0])
    
    # Get the newest version
    newest_version_info = sorted_versions[-1]
    newest_base_version = newest_version_info[1]
    newest_version_tags = newest_version_info[2]
    
    # If we have a current variant, try to find a matching tag with the newest version
    if current_variant:
        # Look for exact variant match in the newest version
        for tag in newest_version_tags:
            tag_variant_match = re.match(r'^v?\d+(\.\d+)*-(.+)$', tag)
            if tag_variant_match and tag_variant_match.group(2) == current_variant:
                return tag
        
        # If we didn't find an exact match, construct one to search for
        variant_search = f"{newest_base_version}-{current_variant}"
        
        # Look for tags that match our constructed variant pattern
        matching_tags = [tag for tag in tags if tag.startswith(variant_search)]
        if matching_tags:
            print(f"Found matching variant for newest version: {matching_tags[0]}")
            return matching_tags[0]
        
        print(f"Warning: Could not find variant '{current_variant}' for newest version {newest_base_version}")
    
    # Fall back to the newest tag, preferring the simplest one
    # If there's a clean version with no variant, use that
    for tag in newest_version_tags:
        if tag == newest_base_version:
            return tag
    
    # Otherwise return the first tag for the newest version
    return newest_version_tags[0]

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