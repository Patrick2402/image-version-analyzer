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
            from packaging import version
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