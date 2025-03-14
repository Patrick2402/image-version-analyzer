# Report Samples

This document shows examples of the various report formats supported by the Docker Image Version Analyzer.

## Command Line Options

```bash
# Basic text output (default)
python main.py Dockerfile --tags

# Generate JSON report
python main.py Dockerfile --tags --output json

# Generate HTML report and save to file
python main.py Dockerfile --tags --output html --report-file report.html

# Generate CSV report without timestamp
python main.py Dockerfile --tags --output csv --no-timestamp --report-file results.csv

# Generate Markdown report 
python main.py Dockerfile --tags --output markdown --report-file report.md
```

## Sample Reports

Below are examples of output in different formats.

### Text Format (Default)

```
Analysis Time: 2023-06-15 14:30:25

Found 2 image(s) in Dockerfile:
1. python:3.9-alpine
2. node:16

==================================================
ANALYSIS SUMMARY
==================================================

⛔ 2 OUTDATED IMAGE(S):
  - python:3.9-alpine : Image is 3 minor version(s) behind
  - node:16 : Image is 2 major version(s) behind

⛔ RESULT: OUTDATED - At least one image is outdated beyond threshold
```

### JSON Format

```json
{
  "timestamp": "2023-06-15 14:30:25",
  "total_images": 2,
  "results": [
    {
      "image": "python:3.9-alpine",
      "status": "OUTDATED",
      "current": "3.9",
      "recommended": "3.12",
      "gap": 3,
      "message": "Image is 3 minor version(s) behind"
    },
    {
      "image": "node:16",
      "status": "OUTDATED",
      "current": "16",
      "recommended": "18",
      "gap": 2,
      "message": "Image is 2 major version(s) behind"
    }
  ],
  "summary": {
    "total": 2,
    "outdated": 2,
    "warnings": 0,
    "unknown": 0,
    "up_to_date": 0
  }
}
```

### CSV Format

```csv
image,status,current,recommended,gap,message
python:3.9-alpine,OUTDATED,3.9,3.12,3,Image is 3 minor version(s) behind
node:16,OUTDATED,16,18,2,Image is 2 major version(s) behind
```

### Markdown Format

```markdown
# Docker Image Analysis Report
*Generated on: 2023-06-15 14:30:25*

## Found 2 image(s)
| # | Image |
| --- | --- |
| 1 | `python:3.9-alpine` |
| 2 | `node:16` |

## Analysis Summary

### Detailed Results
| Image | Status | Current | Recommended | Gap | Message |
| --- | --- | --- | --- | --- | --- |
| `python:3.9-alpine` | ⛔ OUTDATED | 3.9 | 3.12 | 3 | Image is 3 minor version(s) behind |
| `node:16` | ⛔ OUTDATED | 16 | 18 | 2 | Image is 2 major version(s) behind |

## Conclusion
⛔ **RESULT: OUTDATED** - At least one image is outdated beyond threshold

### Outdated Images
- `python:3.9-alpine`: 3.9 → 3.12 (Image is 3 minor version(s) behind)
- `node:16`: 16 → 18 (Image is 2 major version(s) behind)
```

### HTML Format

HTML output creates a nicely formatted web page with:
- Colorful status indicators
- Tables for easy reading
- Summary statistics
- Responsive design

Screenshot: (HTML output would be rendered as a complete webpage with styling)

## Integration with CI/CD

You can integrate these reports into CI/CD pipelines:

### GitHub Actions Example
```yaml
- name: Analyze Docker images
  run: python main.py Dockerfile --tags --output markdown --report-file report.md

- name: Upload report as artifact
  uses: actions/upload-artifact@v3
  with:
    name: docker-image-analysis
    path: report.md
```

### GitLab CI Example
```yaml
analyze_dockerfile:
  stage: test
  script:
    - python main.py Dockerfile --tags --output html --report-file report.html
  artifacts:
    paths:
      - report.html
```

## Recommendations

- Use **Text** format for console output and quick reviews
- Use **JSON** format for programmatic processing or integration with other tools
- Use **CSV** format for importing into spreadsheets or databases
- Use **Markdown** format for GitHub/GitLab documentation
- Use **HTML** format for comprehensive human-readable reports that can be shared