import re
import os.path

def extract_base_images(dockerfile_path, no_info):
    """Extracts all base images from a Dockerfile, including multiple FROM instructions."""
    try:
        if not os.path.isfile(dockerfile_path):
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
            
            if not no_info:
                for image in images:
                    print(f"Image: {image['image']}, Stage: {image['stage']}")
            
            return images
    except Exception as e:
        print(f"Error: {str(e)}")
        return []