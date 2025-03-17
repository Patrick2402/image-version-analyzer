import json
import os.path

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