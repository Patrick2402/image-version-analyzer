# Docker Image Ignore Examples

This document provides examples for using the image ignore features in the Docker Image Version Analyzer.

## Ignore Patterns

The analyzer supports several types of ignore patterns:

1. **Simple Wildcards**: Basic pattern matching with `*` and `?` wildcards
2. **Regex Patterns**: More advanced pattern matching using regular expressions

## Command Line Options

```bash
# Ignore a specific image
python run.py Dockerfile --tags --ignore python:3.9-alpine

# Ignore multiple images
python run.py Dockerfile --tags --ignore python:3.9'*' --ignore node:16

# Ignore images using a pattern file
python run.py Dockerfile --tags --ignore-images ignore-patterns.txt

# Combine both approaches
python run.py Dockerfile --tags --ignore nginx:1.'*' --ignore-images ignore-patterns.txt
```

## Ignore File Format

The ignore file is a simple text file with one pattern per line:

```
# Lines starting with # are comments
python:3.9*
node:16
nginx:1.*

# Empty lines are ignored

# Use regex: prefix for regex patterns
regex:^debian:(?!11).*
```

## Pattern Types

### Wildcard Patterns

Wildcard patterns use `*` and `?` for matching:

- `*` matches any number of characters
- `?` matches a single character

Examples:
- `python:3.*` - Matches python:3.9, python:3.10, etc.
- `node:1?` - Matches node:10, node:16, node:19, etc.
- `nginx:*-alpine` - Matches any nginx version with alpine suffix

### Regex Patterns

For more complex matching, you can use regular expressions with the `regex:` prefix:

Examples:
- `regex:^python:(3\.[0-9]|2\.7).*$` - Match python 2.7 or python 3.x versions
- `regex:^debian:(?!11).*$` - Match all debian versions except debian:11
- `regex:^postgres:(9|10|11)\.*` - Match only postgres 9.x, 10.x, or 11.x versions

## Use Cases

### Ignoring Specific Versions

```
# Ignore outdated Python versions
python:2.7*
python:3.6*
python:3.7*
```

### Ignoring Base Images in Multi-stage Builds

```
# Only check final images, ignore build stages
golang:*
node:*-builder
```

### Ignoring Certain Distributions

```
# Ignore all Alpine-based images
*:*-alpine
*:*-alpine3.*
```

### Ignoring Images from Specific Registries

```
# Ignore images from private registry that don't have public equivalents
regex:^company-registry\.com/.*
```

## Example Reports

### Text Output (with ignored images)

```
Analysis Time: 2023-06-15 14:30:25

Found 4 image(s) in Dockerfile, 2 ignored.
1. python:3.10-alpine
2. debian:11

Ignored images:
  - node:16
  - nginx:1.19

==================================================
ANALYSIS SUMMARY
==================================================

✅ ALL IMAGES UP-TO-DATE
```

### HTML Report

The HTML report will include a separate section for ignored images, making it clear which images were excluded from the analysis.

## Integration with CI/CD

You can use the ignore feature in CI/CD pipelines to focus on specific images:

```yaml
# GitHub Actions Example
- name: Analyze Docker images
  run: |
    python run.py Dockerfile --tags --output html --report-file report.html \
    --ignore-images .github/docker-ignore-patterns.txt
```

## Best Practices

1. **Document Your Ignored Images**: Always add comments to your ignore files explaining why certain images are ignored
2. **Review Regularly**: Periodically review your ignore patterns to make sure you're not missing important updates
3. **Use Specific Patterns**: Avoid overly broad patterns like `*:*` which could hide important issues
4. **Combine With Rules**: Use ignore patterns together with custom rules for the most effective workflow