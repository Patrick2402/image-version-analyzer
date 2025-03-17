# Docker Image Version Analyzer

A tool for analyzing Docker images in Dockerfiles to identify outdated versions.

## Installation

```bash
pip install image-version-analyzer
```

## Usage
```bash
python3 run.py <path_to_Dockerfile> [options]
```

## Options

### General Options
```
  --tags                       Show available tags for images
  --threshold N                Set the version gap threshold for marking images as outdated (default: 3)
  --level N                    Force specific version level for comparison (1=major, 2=minor, 3=patch)
  --private-registry [REGISTRY] Mark images from specified private registry
  --private-registries-file FILE File containing list of private registries
  --rules FILE                 JSON file with custom rules for specific images
```

### Output Options
```
  --output FORMAT              Specify output format (text, json, html, csv, markdown)
  --report-file PATH           Save analysis results to specified file
  --no-timestamp               Do not include timestamp in the report
```

### Image Ignore Options
```
  --ignore PATTERN             Ignore specific image pattern (wildcards supported, can be specified multiple times)
  --ignore-images FILE         Path to file containing list of images to ignore
```

### Slack Notification Options
```
  --slack-notify               Send notification to Slack about analysis results
  --slack-webhook URL          Webhook URL for Slack notifications (can also use SLACK_WEBHOOK_URL env variable)
  --report-url URL             Include a URL to a detailed report in the Slack notification
```

## Output Formats

The tool supports multiple output formats:

### Text Format (Default)
Displays the analysis results in a human-readable format in the terminal. This includes:
- Summary of analyzed images
- List of outdated images with current and recommended versions
- Warning messages for any images that couldn't be analyzed

Example:
```
Found 3 images in Dockerfile:
1. python:3.9
2. nginx:1.19
3. node:16

Docker Image Analysis Results
----------------------------
Images analyzed: 3
Up-to-date: 1
Outdated: 2
Warnings: 0

Outdated Images:
- nginx:1.19 - Current: 1.19, Recommended: 1.23
- python:3.9 - Current: 3.9, Recommended: 3.11
```

### JSON Format
Outputs the analysis results in JSON format, which is useful for integration with other tools or for further processing.

Example:
```json
{
  "summary": {
    "total": 3,
    "up_to_date": 1,
    "outdated": 2,
    "warnings": 0
  },
  "results": [
    {
      "image": "nginx:1.19",
      "status": "OUTDATED",
      "current": "1.19",
      "recommended": "1.23"
    },
    {
      "image": "python:3.9",
      "status": "OUTDATED",
      "current": "3.9",
      "recommended": "3.11"
    },
    {
      "image": "node:16",
      "status": "UP-TO-DATE"
    }
  ],
  "timestamp": "2023-09-24T15:30:45"
}
```

### Other Formats
The tool also supports HTML, CSV, and Markdown formats for generating reports in different contexts.

## Custom Rules

You can define custom rules for specific images using a JSON file:

Example rules.json format:
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
  }
}
```

## Ignoring Images

You can specify images to ignore using patterns:

Example ignore file format:
```
# Lines starting with # are comments
# Each line is a pattern to ignore
# Wildcard (*) is supported
python:3.9*
nginx:1.1*
# Use regex: prefix for regex patterns
regex:^debian:(?!11).*
```

## Slack Integration

The tool can send notifications to Slack when outdated images are found. This is especially useful for CI/CD pipelines or scheduled checks.

### Setting up Slack Webhook

1. Go to your Slack workspace and create a new app at https://api.slack.com/apps
2. Enable "Incoming Webhooks" feature
3. Add a new webhook to your workspace
4. Select the channel where you want to receive notifications
5. Copy the webhook URL

### Using Slack Notifications

You can provide the webhook URL in two ways:

1. Through command-line option:
```bash
python3 run.py Dockerfile --slack-notify --slack-webhook "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

2. Through environment variable:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ"
python3 run.py Dockerfile --slack-notify
```

### Slack Notification Format

The Slack notification includes:
- Summary of analysis results
- Status indicator with emoji (✅ for all up-to-date, ⚠️ for warnings, ❌ for outdated)
- List of all analyzed images with their status
- Detailed information about outdated images
- System information (hostname, timestamp)
- Link to detailed report (if report URL is provided)

## CI/CD Integration

The tool automatically detects CI/CD environments and adds relevant information to Slack notifications:

### GitHub Actions Example

```yaml
name: Docker Image Analysis

on:
  push:
    paths:
      - '**/Dockerfile'

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install image-version-analyzer
      - name: Analyze Dockerfile
        run: |
          python3 run.py Dockerfile --slack-notify --output json --report-file analysis-report.json
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### GitLab CI Example

```yaml
docker-analysis:
  image: python:3.9-alpine
  script:
    - pip install image-version-analyzer
    - python3 run.py Dockerfile --slack-notify
  only:
    changes:
      - "**/Dockerfile"
      - ".gitlab-ci.yml"
  artifacts:
    paths:
      - analysis-report.json
  variables:
    SLACK_WEBHOOK_URL: ${SLACK_WEBHOOK_URL}
```

## Exit Codes

The tool uses the following exit codes:
- 0: All images are up-to-date or only warnings (no outdated images)
- 1: One or more outdated images found

This makes it easy to integrate with CI/CD pipelines and fail builds when outdated images are detected.