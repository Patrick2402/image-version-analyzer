# Slack Notification Examples for Docker Image Analyzer

This document explains how to set up and use the Slack notification system with the Docker Image Version Analyzer.

## Setting up Slack Webhooks

Before you can send notifications to Slack, you need to set up an incoming webhook:

1. Go to your Slack workspace settings
2. Navigate to "Apps & Integrations"
3. Search for "Incoming Webhooks" and add it to your workspace
4. Click "Add New Webhook to Workspace"
5. Choose the channel where notifications should be sent
6. Copy the webhook URL

## Command Line Options

```bash
# Send notification with webhook URL provided directly
python main.py Dockerfile --tags --slack-notify --slack-webhook https://hooks.slack.com/services/TXXXXXXXX/BXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXX

# Send notification using environment variable (more secure)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/TXXXXXXXX/BXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXX"
python main.py Dockerfile --tags --slack-notify

# Include a link to a full report
python main.py Dockerfile --tags --slack-notify --report-url https://ci.example.com/reports/docker-analysis
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SLACK_WEBHOOK_URL` | Webhook URL for Slack notifications |

## Notification Content

The Slack notification includes:

1. **Summary**: Number of images analyzed, outdated, warnings, and up-to-date
2. **Outdated Images**: List of outdated images with current and recommended versions
3. **Warning Images**: Images with warnings (LTS policy violations, etc.)
4. **Security Issues**: Summary of security vulnerabilities (if security checks are enabled)
5. **Metadata**: Hostname, timestamp, and other contextual information

## Notification Colors

Notifications are color-coded based on status:
- **Green**: All images are up-to-date
- **Yellow**: Some images have warnings or unknown status
- **Red**: One or more images are outdated

## CI/CD Integration

### GitLab CI

```yaml
analyze_images:
  stage: test
  script:
    - python main.py Dockerfile --tags --slack-notify --report-url ${CI_PIPELINE_URL}
  variables:
    SLACK_WEBHOOK_URL: ${SLACK_WEBHOOK_URL}  # Set this in CI/CD variables
```

### GitHub Actions

```yaml
name: Analyze Docker Images

on:
  push:
    paths:
      - 'Dockerfile'

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Analyze Docker images
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: |
          python main.py Dockerfile --tags --slack-notify \
            --report-url "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

## Customization

You can modify the `slack_notifier.py` file to customize the notification content and appearance:

- Change the notification format in the `_build_payload` method
- Add more fields or sections to the message
- Customize the emojis and colors used
- Add more metadata to the context section

## Best Practices

1. **Use Environment Variables**: Store webhook URLs in environment variables rather than passing them directly on the command line or hardcoding them
2. **Include Context**: Add relevant context like repository name, branch, and commit ID when using in CI/CD pipelines
3. **Set Channel Carefully**: Choose an appropriate channel for notifications to avoid noise
4. **Add Report URLs**: When possible, include a URL to a more detailed report
5. **Throttle Notifications**: For frequent checks, consider only sending notifications when status changes

## Example Notification

![Example Slack Notification](slack_notification_example.png)