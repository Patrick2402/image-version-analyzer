# Setting Up Slack Notifications: Step-by-Step Guide

This guide walks you through the process of setting up Slack notifications for Docker Image Analyzer results, from Slack workspace configuration to running your first notification.

## Step 1: Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** and select **From scratch**
3. Enter a name (e.g., "Docker Image Analyzer") and select your workspace
4. Click **Create App**

## Step 2: Configure Incoming Webhooks

1. In your app's settings page, click on **Incoming Webhooks** in the left sidebar
2. Toggle the switch to turn on **Activate Incoming Webhooks**
3. Scroll down and click **Add New Webhook to Workspace**
4. Select the channel where you want to receive notifications
5. Click **Allow** to authorize the webhook
6. Copy the webhook URL that appears (it should look like `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX`)

## Step 3: Set Up Your Environment

1. Store the webhook URL in an environment variable (recommended for security):

   ```bash
   # Linux/macOS
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
   
   # Windows (Command Prompt)
   set SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
   
   # Windows (PowerShell)
   $env:SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
   ```

2. Alternatively, you can pass it directly on the command line (not recommended for shared environments):

   ```bash
   python main.py Dockerfile --tags --slack-notify --slack-webhook "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
   ```

## Step 4: Test the Notification

Run a simple test to ensure the integration is working:

```bash
python main.py Dockerfile --tags --slack-notify
```

You should see a message like "✅ Slack notification sent successfully" if everything is configured correctly.

## Step 5: Customize Your Notifications

The default notifications include:
- Basic analysis results
- List of outdated images
- Host and time information

You can customize them by:

1. Adding a report URL:
   ```bash
   python main.py Dockerfile --tags --slack-notify --report-url "https://example.com/reports/123"
   ```

2. Adding custom context for CI/CD pipelines:
   ```bash
   # These are detected automatically in CI environments
   export CI_PIPELINE_URL="https://gitlab.com/example/project/-/pipelines/123"
   export GITHUB_REPOSITORY="username/repo"
   export GITHUB_RUN_ID="12345"
   
   python main.py Dockerfile --tags --slack-notify
   ```

3. Modifying the `slack_notifier.py` file to customize the message format

## Step 6: Integration with CI/CD

### GitLab CI

Add to your `.gitlab-ci.yml`:

```yaml
docker_image_check:
  stage: test
  script:
    - pip install -r requirements.txt
    - python main.py Dockerfile --tags --slack-notify
  variables:
    SLACK_WEBHOOK_URL: ${SLACK_WEBHOOK_URL}  # Set in CI/CD variables
```

### GitHub Actions

Add to your workflow file:

```yaml
name: Docker Image Check

on:
  push:
    paths:
      - 'Dockerfile'

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Check Docker images
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: python main.py Dockerfile --tags --slack-notify
```

## Troubleshooting

### No notification is sent

1. Check that the webhook URL is correct
2. Ensure you have `--slack-notify` in your command
3. Check the console output for any error messages
4. Try adding `--slack-webhook` explicitly even if using environment variables

### Error: Invalid payload

This usually means your notification payload is malformed. Common causes:
- Too many blocks (Slack limits to 50 blocks per message)
- Invalid characters in message

### Rate limiting

Slack has rate limits on webhook usage:
- 1 message per second per webhook by default
- Burst rate may vary

## Security Considerations

- Never commit webhook URLs to version control
- Use environment variables or CI/CD secrets to store webhook URLs
- Consider creating separate webhooks for different environments (dev, staging, prod)
- Rotate webhook URLs periodically for enhanced security