#!/usr/bin/env python3
import sys
import os.path
from dockerfile_parser import extract_base_images
from image_analyzer import analyze_image_tags
from utils import parse_private_registries, load_custom_rules

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <path_to_Dockerfile> [options]")
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