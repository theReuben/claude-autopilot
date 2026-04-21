#!/usr/bin/env python3
"""
============================================================================
Game Agent System — Slack Integration
============================================================================
Unified Slack module for all communication. Handles:
  - Outbound: progress reports, alerts, session updates, ETA reports
  - Inbound: reads feedback from a Slack channel → writes to FEEDBACK.md

Channels:
  #game-agent-progress  — Daily reports, ETAs, session summaries
  #game-agent-alerts    — Stalls, errors, phase completions, gate results
  #game-agent-feedback  — YOU post here, automation picks it up

Setup:
  1. Create a Slack App: https://api.slack.com/apps
  2. Add Bot Token Scopes: chat:write, channels:history, channels:read
  3. Install to workspace, copy Bot User OAuth Token
  4. Create the 3 channels, invite the bot to each
  5. Set environment variables (see below)

Environment:
  SLACK_BOT_TOKEN       — xoxb-... Bot User OAuth Token
  SLACK_PROGRESS_CHANNEL — Channel ID for progress (e.g., C07XXXXXX)
  SLACK_ALERTS_CHANNEL   — Channel ID for alerts
  SLACK_FEEDBACK_CHANNEL — Channel ID for feedback (you post here)

To find channel IDs: right-click channel → View channel details → copy ID at bottom.
============================================================================
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

# ─── Config ─────────────────────────────────────────────────────────────────

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_PROGRESS_CHANNEL = os.environ.get("SLACK_PROGRESS_CHANNEL", "")
SLACK_ALERTS_CHANNEL = os.environ.get("SLACK_ALERTS_CHANNEL", "")
SLACK_FEEDBACK_CHANNEL = os.environ.get("SLACK_FEEDBACK_CHANNEL", "")
PROJECT_DIR = os.environ.get("GAME_AGENT_PROJECT_DIR", os.path.dirname(os.path.abspath(__file__)))
FEEDBACK_FILE = os.path.join(PROJECT_DIR, "FEEDBACK.md")
LAST_FEEDBACK_TS_FILE = os.path.join(PROJECT_DIR, ".automation", "last_feedback_ts")


def _slack_api(method, payload):
    """Make a Slack Web API call."""
    if not SLACK_BOT_TOKEN:
        print("  [Slack] SLACK_BOT_TOKEN not set — skipping")
        return None
    url = f"https://slack.com/api/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode("utf-8"))
        if not result.get("ok"):
            print(f"  [Slack] API error: {result.get('error', 'unknown')}")
        return result
    except Exception as e:
        print(f"  [Slack] Request failed: {e}")
        return None


# ─── Outbound: Post Messages ───────────────────────────────────────────────

def post_message(channel, text, blocks=None, thread_ts=None):
    """Post a message to a Slack channel."""
    payload = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return _slack_api("chat.postMessage", payload)


def post_progress(text, blocks=None):
    """Post to #game-agent-progress."""
    if not SLACK_PROGRESS_CHANNEL:
        print("  [Slack] SLACK_PROGRESS_CHANNEL not set")
        return
    return post_message(SLACK_PROGRESS_CHANNEL, text, blocks)


def post_alert(text, blocks=None):
    """Post to #game-agent-alerts."""
    if not SLACK_ALERTS_CHANNEL:
        print("  [Slack] SLACK_ALERTS_CHANNEL not set")
        return
    return post_message(SLACK_ALERTS_CHANNEL, text, blocks)


# ─── Block Kit Builders ────────────────────────────────────────────────────

def header_block(text):
    return {"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}

def section_block(text):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

def fields_block(fields):
    """fields: list of (label, value) tuples"""
    return {
        "type": "section",
        "fields": [{"type": "mrkdwn", "text": f"*{label}*\n{value}"} for label, value in fields],
    }

def divider_block():
    return {"type": "divider"}

def context_block(text):
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}

def progress_bar(percent, width=20):
    """Text-based progress bar for Slack."""
    filled = int(width * percent / 100)
    empty = width - filled
    return f"`{'█' * filled}{'░' * empty}` {percent}%"


# ─── Formatted Messages ────────────────────────────────────────────────────

def send_session_start(session_num, phase, step, model, remaining_min):
    """Post when a session starts."""
    post_progress(
        f"Session #{session_num} starting",
        blocks=[
            section_block(
                f"▶️ *Session #{session_num}* starting\n"
                f"Phase {phase} · Step {step} · Model: `{model}` · ~{remaining_min}m remaining in window"
            ),
        ],
    )


def send_session_end(session_num, phase, step, new_step, advances):
    """Post when a session completes."""
    if new_step != step:
        status = f"✅ Advanced: `{step}` → `{new_step}`"
    else:
        status = f"🔄 Still on `{step}` (in progress)"

    post_progress(
        f"Session #{session_num} complete",
        blocks=[
            section_block(f"⏹ *Session #{session_num}* complete\n{status}"),
        ],
    )


def send_window_summary(session_count, final_step, duration_min, phase):
    """Post when a window drain finishes."""
    post_progress(
        f"Window complete: {session_count} sessions",
        blocks=[
            header_block("🔋 Window Complete"),
            fields_block([
                ("Sessions", str(session_count)),
                ("Duration", f"{duration_min} min"),
                ("Final Step", final_step),
                ("Phase", phase),
            ]),
            divider_block(),
            context_block(f"Next window starts in ~5.5 hours · {datetime.now().strftime('%H:%M:%S')}"),
        ],
    )


def send_daily_report(progress, etas, blockers, git_stats, recent_logs):
    """Post the daily progress report to Slack."""
    pct = progress["percent"]

    # Header
    blocks = [
        header_block(f"📊 Daily Report — {datetime.now().strftime('%A, %b %d')}"),
        divider_block(),
    ]

    # Progress overview
    blocks.append(fields_block([
        ("Progress", f"{progress_bar(pct)}\n{progress['substeps_done']}/{progress['substeps_total']} substeps"),
        ("Current", f"Phase {progress['phase']} · Step {progress['step']}"),
        ("Next Action", progress["next_action"][:100]),
        ("Last 24h", f"{sum(int(l.get('sessions', 0)) for l in recent_logs)} sessions · {git_stats['commits']} commits"),
    ]))

    # ETAs
    if etas.get("overall_eta"):
        blocks.append(divider_block())
        blocks.append(section_block(f"*📅 Estimated Completion: {etas['overall_eta']}*  ({etas.get('overall_days_remaining', '?')} days)"))

        velocity = etas.get("weighted_velocity", 0)
        trend = etas.get("trend", "")
        trend_emoji = {"accelerating": "📈", "slowing": "📉", "steady": "➡️"}.get(trend, "")
        confidence = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(etas.get("confidence", ""), "")

        blocks.append(context_block(
            f"Velocity: *{velocity}* substeps/day {trend_emoji} {trend} · Confidence: {confidence} {etas.get('confidence', '')}"
        ))

        # Per-phase ETAs
        phase_lines = []
        phase_names = {"1": "Foundation", "2": "Asset Pipeline", "3": "Game Systems", "4": "Polish"}
        for pnum in sorted(etas.get("phase_etas", {}).keys()):
            pe = etas["phase_etas"][pnum]
            name = phase_names.get(pnum, f"Phase {pnum}")
            if pe["status"] == "complete":
                phase_lines.append(f"✅ *Phase {pnum}* ({name}): Complete")
            elif pe["status"] == "in_progress":
                phase_lines.append(f"🔨 *Phase {pnum}* ({name}): {progress_bar(pe['percent'], 10)} → {pe['eta']} (~{pe['days_remaining']}d)")
            else:
                phase_lines.append(f"⬜ *Phase {pnum}* ({name}): {pe['eta']} (~{pe['days_remaining']}d)")

        blocks.append(section_block("\n".join(phase_lines)))
    elif etas.get("message"):
        blocks.append(section_block(f"ℹ️ {etas['message']}"))

    # Blockers
    blocks.append(divider_block())
    if blockers:
        blocker_text = "\n".join(f"🚨 {b}" for b in blockers)
        blocks.append(section_block(f"*Blockers*\n{blocker_text}"))
    else:
        blocks.append(section_block("✅ *No blockers* — everything running smoothly"))

    # Git summary
    if git_stats["commits"] > 0:
        blocks.append(divider_block())
        # Truncate to fit Slack block limits (3000 chars)
        summary = git_stats.get("summary", "")[:2000]
        blocks.append(section_block(f"*Recent Commits*\n```{summary}```"))

    blocks.append(divider_block())
    blocks.append(context_block(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · Game Agent System"))

    post_progress("Daily Report", blocks=blocks)


def send_alert(event_type, detail=""):
    """Send a notification to #game-agent-alerts."""
    alerts = {
        "phase_complete": ("🎉", f"*Phase {detail} Complete!*\nGate passed. Advancing to Phase {int(detail)+1 if detail.isdigit() else '?'}."),
        "stall": ("🚨", f"*Build STALLED on Step {detail}*\nSame step for 5+ sessions. Manual intervention likely needed."),
        "project_complete": ("🏆", "*PROJECT COMPLETE!*\nAll 4 phases done. Time to test the full pipeline."),
        "error": ("⚠️", f"*Automation Error*\n{detail}"),
        "gate_failed": ("🚫", f"*Phase {detail} Gate FAILED*\nFix issues before advancing. Check logs."),
        "gate_passed": ("✅", f"*Phase {detail} Gate Passed*\nAll checks clear."),
        "milestone": ("🏁", f"*Milestone: {detail}*"),
    }

    emoji, text = alerts.get(event_type, ("ℹ️", f"{event_type}: {detail}"))
    post_alert(
        f"{emoji} {text}",
        blocks=[
            section_block(f"{emoji} {text}"),
            context_block(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ],
    )


# ─── Inbound: Read Feedback from Slack ──────────────────────────────────────

def sync_feedback():
    """
    Read new messages from #game-agent-feedback and append them to FEEDBACK.md.
    Tracks the timestamp of the last read message to avoid duplicates.
    Only picks up messages from humans (ignores bot messages).
    """
    if not SLACK_FEEDBACK_CHANNEL:
        print("  [Slack] SLACK_FEEDBACK_CHANNEL not set — skipping feedback sync")
        return 0

    # Load last read timestamp
    os.makedirs(os.path.dirname(LAST_FEEDBACK_TS_FILE), exist_ok=True)
    last_ts = "0"
    if os.path.exists(LAST_FEEDBACK_TS_FILE):
        last_ts = Path(LAST_FEEDBACK_TS_FILE).read_text().strip()

    # Fetch messages since last read
    payload = {
        "channel": SLACK_FEEDBACK_CHANNEL,
        "oldest": last_ts,
        "limit": 50,
    }
    # Use GET-style params for conversations.history
    params = "&".join(f"{k}={v}" for k, v in payload.items())
    url = f"https://slack.com/api/conversations.history?{params}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [Slack] Failed to fetch feedback: {e}")
        return 0

    if not result.get("ok"):
        print(f"  [Slack] API error: {result.get('error')}")
        return 0

    messages = result.get("messages", [])
    # Filter: only human messages (no bots), newer than last_ts
    human_messages = [
        m for m in messages
        if not m.get("bot_id")
        and not m.get("subtype")
        and float(m.get("ts", "0")) > float(last_ts)
    ]

    if not human_messages:
        print("  [Slack] No new feedback messages")
        return 0

    # Sort oldest first
    human_messages.sort(key=lambda m: float(m["ts"]))

    # Append to FEEDBACK.md
    lines = []
    for msg in human_messages:
        ts = datetime.fromtimestamp(float(msg["ts"])).strftime("%Y-%m-%d %H:%M")
        text = msg.get("text", "").strip()
        # Handle file attachments
        files = msg.get("files", [])
        file_notes = ""
        if files:
            file_names = ", ".join(f.get("name", "file") for f in files)
            file_notes = f"\n  (Attached files: {file_names} — download from Slack if needed)"
        lines.append(f"\n[UNREAD] [{ts}] {text}{file_notes}\n")

    if lines:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.writelines(lines)

        # Update last read timestamp
        latest_ts = human_messages[-1]["ts"]
        Path(LAST_FEEDBACK_TS_FILE).write_text(latest_ts, encoding="utf-8")

        # Acknowledge in Slack
        post_message(
            SLACK_FEEDBACK_CHANNEL,
            f"📥 Picked up {len(human_messages)} feedback item(s). Will be addressed in the next session.",
        )

        print(f"  [Slack] Synced {len(human_messages)} feedback messages to FEEDBACK.md")

    return len(human_messages)


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  slack.py sync-feedback          — Pull feedback from Slack → FEEDBACK.md")
        print("  slack.py alert <type> [detail]   — Send alert to #alerts")
        print("  slack.py session-start <#> <phase> <step> <model> <min>")
        print("  slack.py session-end <#> <phase> <step> <new_step>")
        print("  slack.py window-summary <sessions> <step> <duration> <phase>")
        print("  slack.py test                    — Send a test message")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "sync-feedback":
        count = sync_feedback()
        sys.exit(0 if count >= 0 else 1)

    elif cmd == "alert":
        event_type = sys.argv[2] if len(sys.argv) > 2 else "error"
        detail = sys.argv[3] if len(sys.argv) > 3 else ""
        send_alert(event_type, detail)

    elif cmd == "session-start":
        send_session_start(
            session_num=sys.argv[2],
            phase=sys.argv[3],
            step=sys.argv[4],
            model=sys.argv[5],
            remaining_min=sys.argv[6],
        )

    elif cmd == "session-end":
        send_session_end(
            session_num=sys.argv[2],
            phase=sys.argv[3],
            step=sys.argv[4],
            new_step=sys.argv[5],
            advances=[],
        )

    elif cmd == "window-summary":
        send_window_summary(
            session_count=sys.argv[2],
            final_step=sys.argv[3],
            duration_min=sys.argv[4],
            phase=sys.argv[5],
        )

    elif cmd == "test":
        post_progress("🧪 Test message from Game Agent automation", blocks=[
            header_block("🧪 Test Message"),
            section_block("If you see this, Slack integration is working correctly."),
            fields_block([("Status", "Connected"), ("Time", datetime.now().strftime("%H:%M:%S"))]),
        ])
        post_alert("test", "Test alert — Slack integration is working")
        print("Test messages sent to progress and alerts channels")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
