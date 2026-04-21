#!/usr/bin/env python3
"""
============================================================================
Push Notifications — Critical Event Alerts
============================================================================
Sends immediate notifications for events that shouldn't wait until the
daily report. Called by run-session.sh when it detects these events.

Usage:
  python3 notify.py phase_complete 1
  python3 notify.py stall 2.3
  python3 notify.py project_complete
  python3 notify.py error "WebSocket bridge failed to compile"
  python3 notify.py gate_failed 1
  python3 notify.py gate_passed 1
  python3 notify.py milestone "First end-to-end test passed"

Notification channels (configure via environment):
  EMAIL:     Always (uses same SMTP as daily-report.py)
  NTFY:      Set NTFY_TOPIC for push to phone (free, no account needed)
  SLACK:     Set SLACK_WEBHOOK_URL for team channel
  DISCORD:   Set DISCORD_WEBHOOK_URL for Discord channel
============================================================================
"""

import os
import sys
import json
import smtplib
import urllib.request
import urllib.error
from datetime import datetime
from email.mime.text import MIMEText

# ─── Config ────────────────────────────────────────────────────────────────

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_TO = os.environ.get("EMAIL_TO", SMTP_USER)

# ntfy.sh — free push notifications to phone, no account required
# Setup: install ntfy app on phone, subscribe to your topic name
# Docs: https://ntfy.sh
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # e.g., "gameagent-reuben-xyz"

# Slack webhook
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")

# Discord webhook
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

# ─── Event Definitions ─────────────────────────────────────────────────────

EVENTS = {
    "phase_complete": {
        "emoji": "🎉",
        "title": "Phase {detail} Complete!",
        "body": "Phase {detail} has passed its gate validation and is complete. Automation will now begin Phase {next_phase}.",
        "priority": "high",
    },
    "stall": {
        "emoji": "🚨",
        "title": "Build STALLED on Step {detail}",
        "body": "The same step has not advanced in 5+ consecutive sessions. Manual intervention likely needed. Check PROGRESS.md and recent logs.",
        "priority": "urgent",
    },
    "project_complete": {
        "emoji": "🏆",
        "title": "PROJECT COMPLETE!",
        "body": "All 4 phases are done. The game agent system has been fully built. Time to test the full pipeline.",
        "priority": "high",
    },
    "error": {
        "emoji": "⚠️",
        "title": "Automation Error",
        "body": "{detail}",
        "priority": "default",
    },
    "gate_failed": {
        "emoji": "🚫",
        "title": "Phase {detail} Gate FAILED",
        "body": "The phase gate validation failed. Automation will attempt to fix issues before retrying. Check phase-gate.py output in logs.",
        "priority": "high",
    },
    "gate_passed": {
        "emoji": "✅",
        "title": "Phase {detail} Gate Passed",
        "body": "Phase {detail} gate validation passed. All required files exist, code compiles, and handlers are correctly implemented.",
        "priority": "default",
    },
    "milestone": {
        "emoji": "🏁",
        "title": "Milestone: {detail}",
        "body": "A significant milestone was reached: {detail}",
        "priority": "default",
    },
}

# ─── Send Functions ─────────────────────────────────────────────────────────

def send_email(subject, body):
    if not SMTP_USER or not SMTP_PASS:
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = f"[Game Agent] {subject}"
        msg["From"] = SMTP_USER
        msg["To"] = EMAIL_TO
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"  Email sent to {EMAIL_TO}")
    except Exception as e:
        print(f"  Email failed: {e}")


def send_ntfy(title, body, priority="default"):
    if not NTFY_TOPIC:
        return
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "robot,hammer",
            },
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  ntfy push sent to topic '{NTFY_TOPIC}'")
    except Exception as e:
        print(f"  ntfy failed: {e}")


def send_slack(title, body):
    if not SLACK_WEBHOOK:
        return
    try:
        payload = json.dumps({"text": f"*{title}*\n{body}"}).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  Slack notification sent")
    except Exception as e:
        print(f"  Slack failed: {e}")


def send_discord(title, body):
    if not DISCORD_WEBHOOK:
        return
    try:
        payload = json.dumps({
            "embeds": [{
                "title": title,
                "description": body,
                "color": 5814783,  # Purple
                "timestamp": datetime.now().isoformat(),
            }]
        }).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  Discord notification sent")
    except Exception as e:
        print(f"  Discord failed: {e}")


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: notify.py <event_type> [detail]")
        print(f"Events: {', '.join(EVENTS.keys())}")
        sys.exit(1)

    event_type = sys.argv[1]
    detail = sys.argv[2] if len(sys.argv) > 2 else ""

    if event_type not in EVENTS:
        print(f"Unknown event: {event_type}")
        sys.exit(1)

    event = EVENTS[event_type]
    next_phase = str(int(detail) + 1) if detail.isdigit() else "?"

    title = f"{event['emoji']} {event['title'].format(detail=detail, next_phase=next_phase)}"
    body = event["body"].format(detail=detail, next_phase=next_phase)
    body += f"\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    priority = event["priority"]

    print(f"Sending notification: {title}")
    send_email(title, body)
    send_ntfy(title, body, priority)
    send_slack(title, body)
    send_discord(title, body)


if __name__ == "__main__":
    main()
