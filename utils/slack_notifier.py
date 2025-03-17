import json
import urllib.request
import urllib.error
import datetime
import socket
import os
import sys

class SlackNotifier:
    """
    Class for sending Docker image analysis notifications to Slack.
    """
    
    def __init__(self, webhook_url=None):
        """
        Initialize the Slack notifier.
        
        Args:
            webhook_url: Slack webhook URL (can also be set via environment variable SLACK_WEBHOOK_URL)
        """
        self.webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            print("Warning: No Slack webhook URL provided. Notifications will not be sent.")
    
    def send_notification(self, results, dockerfile_path, additional_info=None):
        """
        Send a notification to Slack with analysis results.
        
        Args:
            results: List of analysis results
            dockerfile_path: Path to the analyzed Dockerfile
            additional_info: Additional information to include (dict)
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        if not self.webhook_url:
            return False
        
        try:
            # Build the message payload
            payload = self._build_payload(results, dockerfile_path, additional_info)
            
            # Send the message
            return self._send_payload(payload)
        except Exception as e:
            print(f"Error sending Slack notification: {str(e)}")
            return False
    
    def _build_payload(self, results, dockerfile_path, additional_info=None):
        """
        Build the Slack message payload.
        
        Args:
            results: List of analysis results
            dockerfile_path: Path to the analyzed Dockerfile
            additional_info: Additional information to include
            
        Returns:
            dict: Slack message payload
        """
        # Get summary info
        summary = self._get_summary(results)
        
        # Determine color based on status
        color = "#36a64f"  # Green
        if summary['outdated'] > 0:
            color = "#ff0000"  # Red
        elif summary['warnings'] > 0 or summary['unknown'] > 0:
            color = "#ffcc00"  # Yellow
        
        # Create main attachment text
        text = f"Docker Image Analysis for `{dockerfile_path}`"
        
        # Build blocks
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Docker Image Analysis Report*\n{text}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Images Analyzed:*\n{summary['total']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{self._get_status_emoji(summary)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Up-to-date:*\n{summary['up_to_date']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Outdated:*\n{summary['outdated']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Warnings:*\n{summary['warnings']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Unknown:*\n{summary['unknown']}"
                    }
                ]
            }
        ]
        
        # Dodaj listę wszystkich analizowanych obrazów
        filtered_results = [r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY']
        all_images_text = "*Analizowane obrazy:*\n"
        for result in filtered_results:
            if 'image' in result:
                status_emoji = "✅" if result.get('status') == 'UP-TO-DATE' else "❌" if result.get('status') == 'OUTDATED' else "⚠️"
                all_images_text += f"{status_emoji} `{result['image']}`\n"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": all_images_text
            }
        })
        
        # Add outdated images section if any
        if summary['outdated_images']:
            outdated_text = "*Outdated Images:*\n"
            for img in summary['outdated_images']:
                current = img.get('current', 'N/A')
                recommended = img.get('recommended', 'N/A')
                outdated_text += f"• `{img['image']}` - {current} → {recommended}\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": outdated_text
                }
            })
        
        # Add warning images section if any
        if summary['warning_images']:
            warning_text = "*Warning Images:*\n"
            for img in summary['warning_images']:
                warning_text += f"• `{img['image']}` - {img['message']}\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": warning_text
                }
            })
        
        # Add security info if available
        has_security = False
        vulnerable_count = 0
        for result in results:
            if 'security' in result and result['security']['status'] == 'VULNERABLE':
                has_security = True
                vulnerable_count += 1
        
        if has_security:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Security Issues:*\n{vulnerable_count} images have security vulnerabilities"
                }
            })
        
        # Add context with metadata
        hostname = socket.gethostname()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        context_elements = [
            {
                "type": "mrkdwn",
                "text": f"*Host:* {hostname}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Time:* {timestamp}"
            }
        ]
        
        # Add any additional info to context
        if additional_info:
            for key, value in additional_info.items():
                context_elements.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:* {value}"
                })
        
        blocks.append({
            "type": "context",
            "elements": context_elements
        })
        
        # Add view details button if provided in additional_info
        if additional_info and 'report_url' in additional_info:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Full Report"
                        },
                        "url": additional_info['report_url'],
                        "style": "primary"
                    }
                ]
            })
        
        # Build the final payload
        payload = {
            "blocks": blocks,
            "attachments": [
                {
                    "color": color,
                    "blocks": []
                }
            ]
        }
        
        return payload
    
    def _get_summary(self, results):
        """Get summary stats of results"""
        # Filter out special entries
        filtered_results = [r for r in results if r.get('image') != 'IGNORED_IMAGES_SUMMARY']
        
        outdated = [r for r in filtered_results if r.get('status') == 'OUTDATED']
        warnings = [r for r in filtered_results if r.get('status') == 'WARNING']
        unknown = [r for r in filtered_results if r.get('status') == 'UNKNOWN']
        up_to_date = [r for r in filtered_results if r.get('status') == 'UP-TO-DATE']
        
        return {
            'total': len(filtered_results),
            'outdated': len(outdated),
            'warnings': len(warnings),
            'unknown': len(unknown),
            'up_to_date': len(up_to_date),
            'outdated_images': outdated,
            'warning_images': warnings,
            'unknown_images': unknown,
            'up_to_date_images': up_to_date
        }
    
    def _get_status_emoji(self, summary):
        """Get status message with emoji"""
        if summary['outdated'] > 0:
            return "❌ Outdated"
        elif summary['warnings'] > 0 or summary['unknown'] > 0:
            return "⚠️ Warning"
        else:
            return "✅ All Up-to-date"
    
    def _send_payload(self, payload):
        """
        Send the payload to Slack.
        
        Args:
            payload: Slack message payload
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            # Convert payload to JSON
            data = json.dumps(payload).encode('utf-8')
            
            # Create request
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            # Send request
            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except urllib.error.HTTPError as e:
            print(f"HTTP Error sending Slack notification: {e.code} {e.reason}")
            return False
        except urllib.error.URLError as e:
            print(f"URL Error sending Slack notification: {e.reason}")
            return False
        except Exception as e:
            print(f"Error sending Slack notification: {str(e)}")
            return False


def send_slack_notification(results, dockerfile_path, webhook_url=None, additional_info=None):
    """
    Convenience function to send a Slack notification.
    
    Args:
        results: Analysis results
        dockerfile_path: Path to Dockerfile
        webhook_url: Slack webhook URL (optional, can also use SLACK_WEBHOOK_URL env var)
        additional_info: Additional info to include in the notification
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    notifier = SlackNotifier(webhook_url)
    return notifier.send_notification(results, dockerfile_path, additional_info)