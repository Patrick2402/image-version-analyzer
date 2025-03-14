# Dockerfile Analyzer

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.6%2B-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

A powerful, intelligent tool for analyzing Docker images in your Dockerfile and detecting outdated versions. Designed for DevOps teams, CI/CD pipelines, and security compliance checks.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Command Line Options](#command-line-options)
  - [Exit Codes](#exit-codes)
- [Advanced Features](#advanced-features)
  - [Version Detection Algorithms](#version-detection-algorithms)
  - [Working with Private Registries](#working-with-private-registries)
  - [Custom Rules System](#custom-rules-system)
  - [Multi-stage Dockerfile Support](#multi-stage-dockerfile-support)
- [Example Outputs](#example-outputs)
- [Integration with CI/CD](#integration-with-cicd)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Overview

Dockerfile Analyzer is a Python-based tool that scans your Dockerfile for base images, connects to Docker Hub (and potentially other registries in the future), and determines if your images are outdated. It intelligently understands different versioning schemes and can apply custom rules to specific images.

The tool provides actionable feedback that can be used in CI/CD pipelines to enforce image update policies or simply to help keep your Docker images up-to-date.

## Key Features

- **Comprehensive Dockerfile Analysis**: Parses and extracts all base images, including multi-stage builds
- **Intelligent Version Comparison**: Automatically detects versioning schemes (major.minor.patch, year.month, etc.)
- **Smart Image Classification**: Recognizes common image types and applies appropriate version level comparisons
- **Custom Rules Engine**: Define specific rules for images with unique update patterns (LTS releases, etc.)
- **Private Registry Support**: Works with images from private registries
- **Detailed Reporting**: Provides comprehensive output on image status with specific upgrade recommendations
- **CI/CD Integration**: Exit codes designed for pipeline integration with customizable thresholds

## How It Works

The analyzer performs the following steps:

1. **Extraction**: Parses the Dockerfile to identify all base images
2. **Analysis**: For each image:
   - Determines the base image name and tag
   - Removes private registry prefix if needed
   - Queries Docker Hub API for available tags
   - Applies intelligent filtering to identify version tags
   - Detects the appropriate version comparison level
   - Applies any custom rules specific to the image
   - Calculates the version gap between current and latest versions
3. **Reporting**: Provides detailed, actionable output with status indicators
4. **Evaluation**: Returns appropriate exit code based on findings and configured thresholds

## Installation

### Prerequisites

- Python 3.6 or higher
- Required Python packages:
  - `packaging` (for semantic version comparison)

### Installation Steps

1. Install the required Python package:
   ```bash
   pip install packaging
   ```

2. Download the script:
   ```bash
   git clone git@github.com:Patrick2402/image-verion-analyzer.git
   ```

3. Make it executable:
   ```bash
   chmod +x main.py
   ```

## Usage

### Basic Usage

To analyze a Dockerfile and check for outdated images:

```bash
python3 main.py /path/to/Dockerfile --tags
```

This will:
1. Extract all base images from the Dockerfile
2. Check available tags from Docker Hub
3. Identify the latest version for each image
4. Show how far behind your current version is
5. Exit with status code 1 if any image is outdated beyond the default threshold (3 versions)

### Command Line Options

The analyzer supports the following command line options:

| Option | Description | Default |
|--------|-------------|---------|
| `--tags` | Show available tags for images | Required |
| `--threshold N` | Set the version gap threshold for marking images as outdated | 3 |
| `--level N` | Force specific version level for comparison (1=major, 2=minor, 3=patch) | Auto-detected |
| `--private-registry REGISTRY` | Specify a private registry to handle | None |
| `--private-registries-file FILE` | File containing list of private registries | None |
| `--rules FILE` | JSON file with custom rules for specific images | None |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - All images are up-to-date or within threshold |
| 1 | Warning - At least one image is outdated beyond threshold |

## Advanced Features

### Version Detection Algorithms

The analyzer uses a combination of methods to determine the appropriate version comparison level:

1. **Knowledge Base**: Contains predefined rules for common images:
   - `debian`, `ubuntu`, `centos`, `node` → Level 1 (major version)
   - `alpine`, `nginx`, `python`, `php`, `golang` → Level 2 (minor version)

2. **Pattern Analysis**: For unknown images, analyzes available tags to determine the common versioning pattern:
   - Extracts version numbers from tags
   - Compares frequency of changes between major/minor/patch
   - Identifies the most significant changing part

3. **Custom Rules**: Applies any user-defined rules that override automatic detection

### Working with Private Registries

To analyze images from private registries:

```bash
python3 main.py Dockerfile --tags --private-registry docker-registry.company.com:5000
```

This will:
1. Identify images with the specified registry prefix
2. Remove the prefix for lookups in Docker Hub
3. Compare versions based on public equivalent

Multiple registries can be specified using a file:

```
# private-registries.txt
docker-registry.company.com:5000
internal-registry.corp.local
```

And then used:

```bash
python3 main.py Dockerfile --tags --private-registries-file private-registries.txt
```

### Custom Rules System

The custom rules system allows fine-grained control over how specific images are analyzed.

Create a JSON file with your rules:

```json
{
  "node": {
    "level": 1,
    "lts_versions": [16, 18, 20, 22, 24],
    "step_by": 2,
    "skip_versions": ["19", "21", "23"]
  },
  "debian": {
    "level": 1
  },
  "python": {
    "level": 2
  },
  "nginx": {
    "level": 2,
    "skip_versions": ["1.19", "1.21"]
  }
}
```

#### Available Rule Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `level` | Integer | Version level to check (1=major, 2=minor, 3=patch) | `"level": 2` |
| `lts_versions` | Array | List of version numbers considered LTS | `"lts_versions": [16, 18, 20]` |
| `step_by` | Integer | For images that follow a step pattern | `"step_by": 2` |
| `skip_versions` | Array | List of version numbers to ignore | `"skip_versions": ["19", "21"]` |

#### Rule Application Logic

- **LTS Policy**: When using an LTS version, the tool suggests upgrading to the next LTS version, not the latest non-LTS version
- **Step-by-N**: Calculates version gaps in terms of "steps" rather than raw version numbers
- **Skip Versions**: Ignores specified versions when calculating the upgrade path

### Multi-stage Dockerfile Support

The analyzer fully supports multi-stage Dockerfiles. It identifies all base images and treats them independently:

```dockerfile
FROM golang:1.19 AS builder
# ...build steps

FROM alpine:3.17
# ...final image steps
```

The analyzer will check both `golang:1.19` and `alpine:3.17` for updates.

## Example Outputs

### Up-to-date Images

```
Found 2 image(s) in Dockerfile:
1. python:3.12-alpine
2. nginx:1.25.3

==================================================
Image 1 of 2: python:3.12-alpine
==================================================
...
Newest semantic version: 3.12
Actual version: 3.12
You are using the latest major version

==================================================
Image 2 of 2: nginx:1.25.3
==================================================
...
Newest semantic version: 1.25.3
Actual version: 1.25.3
You are using the latest minor version

==================================================
DOCKERFILE ANALYSIS SUMMARY
==================================================

✅ ALL IMAGES UP-TO-DATE
```

### Outdated Images

```
Found 2 image(s) in Dockerfile:
1. python:3.9-alpine
2. node:16

...

==================================================
DOCKERFILE ANALYSIS SUMMARY
==================================================

⛔ 2 OUTDATED IMAGE(S):
  - python:3.9-alpine : Image is 3 minor version(s) behind
  - node:16 : Image is 4 major version(s) behind

⛔ RESULT: OUTDATED - At least one image is outdated beyond threshold
```

### With Custom Rules Applied

```
Found 1 image(s) in Dockerfile:
1. node:18

==================================================
Image 1 of 1: node:18
==================================================
Using major version level (1) for comparison
Applying LTS version rule for node: 16, 18, 20, 22, 24
Applying step-by-2 rule for node
...
Newest semantic version: 22
Actual version: 18
Following step-by-2 rule: 18 → 22 (valid)
You are 2 major version(s) behind
Missing versions: 20, 22

STATUS: OUTDATED - Image is 2 major version(s) behind

==================================================
DOCKERFILE ANALYSIS SUMMARY
==================================================

⛔ 1 OUTDATED IMAGE(S):
  - node:18 : Image is 2 major version(s) behind

⛔ RESULT: OUTDATED - At least one image is outdated beyond threshold
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Check Docker Images

on:
  push:
    paths:
      - 'Dockerfile'
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Mondays

jobs:
  check-images:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install dependencies
        run: pip install packaging
          
      - name: Check Docker images
        run: |
          python main.py Dockerfile --tags --threshold 3 --rules rules.json
          
      - name: Notify if outdated
        if: ${{ failure() }}
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Outdated Docker images detected',
              body: 'The Dockerfile contains outdated images. Please update them.'
            })
```

### GitLab CI Example

```yaml
check_images:
  stage: test
  script:
    - pip install packaging
    - python main.py Dockerfile --tags --threshold 3 --rules rules.json
  rules:
    - changes:
        - Dockerfile
    - schedule: '0 0 * * 1'  # Weekly on Mondays
  artifacts:
    paths:
      - image_analysis_report.txt
```

## Known Limitations

- **Docker Hub Only**: Currently only supports checking tags from Docker Hub
- **API Rate Limits**: May encounter rate limiting with heavy usage
- **Tag Filtering**: Some complex tagging schemes might not be correctly identified
- **Limited Registry Support**: Cannot check private registries directly

## Troubleshooting

### Common Issues

1. **"Error: HTTP Error 404: Not Found"**
   - The image may not exist in Docker Hub
   - If using a private registry, ensure the correct format is specified

2. **"Error: HTTP Error 429: Too Many Requests"**
   - You've hit Docker Hub's API rate limits
   - Add delay between checks or reduce frequency

3. **Incorrect Version Analysis**
   - Check if the image needs custom rules
   - Specify the version level manually with `--level`

### Debug Mode

For more detailed output, set the environment variable `DEBUG=1`:

```bash
DEBUG=1 python3 main.py Dockerfile --tags
```

## FAQ

**Q: Why does the tool mark an image as outdated when I'm using an LTS version?**  
A: By default, the tool compares to the latest available version. Use a custom rule with `lts_versions` to enable LTS-aware version comparison.

**Q: Can I check images from private registries directly?**  
A: Currently, the tool can only check versions against Docker Hub. For private registry images, it strips the registry prefix and checks the public equivalent.

**Q: How does the automatic version level detection work?**  
A: The tool analyzes the versioning patterns in available tags, detects which parts of the version number change most frequently, and combines this with knowledge about common images.

**Q: Can I use this in production CI/CD pipelines?**  
A: Yes! The tool is designed for CI/CD integration with configurable thresholds to prevent false positives.

# Docker Image Version Analyzer GUI

Graphical User Interface for the Docker image version analysis tool.

## Requirements

- Python 3.6+
- PyQt5
- packaging

## Installation

To install the required dependencies, use:

```bash
pip install -r requirements.txt
```

## Running the Application

```bash
python gui.py
```

## Features

The GUI application offers all features available in the console version, but with a user-friendly interface:

- Selection of Dockerfile for analysis
- Setting version threshold for determining outdated images
- Selection of version level for comparison (major, minor, patch)
- Adding private registries for analysis
- Loading custom rules from a JSON file
- Displaying analysis logs
- Showing results in a readable table with color-coded status indicators

## Interface Description

### Settings Panel

- **Dockerfile** - Path to the Dockerfile for analysis
- **Version Threshold** - Number of versions after which an image is marked as outdated
- **Version Level** - Determines which version level is considered when comparing:
  - Automatic Detection - The program automatically selects the appropriate level
  - Major Version - Compares only major versions (e.g., 2.x.x vs 3.x.x)
  - Minor Version - Compares major and minor versions (e.g., 2.1.x vs 2.2.x)
  - Patch Version - Compares all version levels (e.g., 2.1.1 vs 2.1.2)
- **Private Registries** - List of private registries separated by commas
- **Rules File** - Path to JSON file with custom rules for specific images

### Tabs

- **Logs** - Displays detailed logs from the analysis process
- **Results** - Presents analysis results in a table with the following columns:
  - Image - Docker image name
  - Status - Image update status (UP-TO-DATE, OUTDATED, WARNING, UNKNOWN)
  - Current Version - Currently used image version
  - Recommended Version - Recommended latest image version
  - Message - Detailed status information

## Status Colors

- **Green (UP-TO-DATE)** - Image is up to date
- **Red (OUTDATED)** - Image is outdated and requires updating
- **Yellow (WARNING)** - Image requires attention (e.g., violates LTS rules)
- **Gray (UNKNOWN)** - Image status could not be determined

## Troubleshooting

- **No Results** - Make sure the Dockerfile is valid and contains FROM instructions
- **Connection Errors** - Check if you have a working internet connection to download tag information
- **Analysis Errors** - Check the logs on the "Logs" tab for detailed error information

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.