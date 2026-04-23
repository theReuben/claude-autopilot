#!/usr/bin/env python3
"""
============================================================================
Game Agent System — Daily Progress Report
============================================================================
Sends a morning email with:
  - Current phase/step and % completion
  - What was accomplished in the last 24 hours
  - Any blockers or stalls
  - Screenshots (Unity, Blender renders, terminal output)
  - Session stats (count, tokens, errors)

Schedule: daily at your preferred morning time via cron/Task Scheduler.

Setup:
  1. pip install --break-system-packages Pillow   (for screenshot capture)
  2. Set environment variables (see CONFIGURATION below)
  3. Schedule: crontab -e → 0 8 * * * python3 /path/to/daily-report.py

Uses Gmail SMTP by default. For other providers, change SMTP_HOST/PORT.
============================================================================
"""

import os
import re
import sys
import glob
import json
import smtplib
import subprocess
import platform
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# ─── Configuration (set via environment variables) ──────────────────────────

PROJECT_DIR = os.environ.get("GAME_AGENT_PROJECT_DIR", os.path.dirname(os.path.abspath(__file__)))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")         # your-email@gmail.com
SMTP_PASS = os.environ.get("SMTP_PASS", "")         # Gmail app password (not regular password)
EMAIL_TO = os.environ.get("EMAIL_TO", SMTP_USER)    # recipient (defaults to sender)
EMAIL_SUBJECT_PREFIX = os.environ.get("EMAIL_SUBJECT_PREFIX", "[Game Agent]")

# ─── Progress Parsing ──────────────────────────────────────────────────────

def parse_progress():
    """Parse PROGRESS.md and return structured data."""
    progress_file = os.path.join(PROJECT_DIR, "PROGRESS.md")
    if not os.path.exists(progress_file):
        return {"phase": "?", "step": "?", "next_action": "Not started", "sessions": [], "steps": {}}

    content = Path(progress_file).read_text(encoding="utf-8")

    # Extract header fields
    phase = re.search(r'\*\*Active Phase:\*\*\s*(.+)', content)
    step = re.search(r'\*\*Active Step:\*\*\s*(.+)', content)
    next_action = re.search(r'\*\*Next Action:\*\*\s*(.+)', content)
    last_summary = re.search(r'\*\*Last Session Summary:\*\*\s*(.+)', content)

    # Count completed vs total substeps (overall)
    done = len(re.findall(r'\[x\]', content, re.IGNORECASE))
    total = len(re.findall(r'\[[ x]\]', content, re.IGNORECASE))

    # Count per-phase substeps
    phases = {}
    phase_sections = re.split(r'^## Phase (\d+):', content, flags=re.MULTILINE)
    # phase_sections = ['header', '1', 'phase1 content', '2', 'phase2 content', ...]
    for i in range(1, len(phase_sections) - 1, 2):
        phase_num = phase_sections[i]
        phase_content = phase_sections[i + 1]
        # Stop at next ## or end
        next_phase = phase_content.split('\n## ')[0] if '\n## ' in phase_content else phase_content
        p_done = len(re.findall(r'\[x\]', next_phase, re.IGNORECASE))
        p_total = len(re.findall(r'\[[ x]\]', next_phase, re.IGNORECASE))
        phases[phase_num] = {
            "done": p_done,
            "total": p_total,
            "percent": round(p_done / p_total * 100, 1) if p_total > 0 else 0,
        }

    # Extract step statuses
    steps = {}
    for match in re.finditer(r'### Step ([\d.]+):.*?\n- \*\*Status:\*\*\s*(\w+)', content):
        steps[match.group(1)] = match.group(2)

    # Extract session log (last 10 entries)
    sessions = []
    log_pattern = re.compile(r'\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|')
    for match in log_pattern.finditer(content):
        sessions.append({
            "number": match.group(1).strip(),
            "date": match.group(2).strip(),
            "step": match.group(3).strip(),
            "done": match.group(4).strip(),
            "next": match.group(5).strip(),
            "issues": match.group(6).strip(),
        })

    return {
        "phase": phase.group(1).strip() if phase else "?",
        "step": step.group(1).strip() if step else "?",
        "next_action": next_action.group(1).strip() if next_action else "?",
        "last_summary": last_summary.group(1).strip() if last_summary else "",
        "substeps_done": done,
        "substeps_total": total,
        "percent": round(done / total * 100, 1) if total > 0 else 0,
        "phases": phases,
        "steps": steps,
        "sessions": sessions[-10:],  # Last 10 sessions
    }


# ─── Velocity Tracking & ETA ───────────────────────────────────────────────

VELOCITY_FILE = os.path.join(PROJECT_DIR, ".automation", "velocity.json")

def load_velocity_history():
    """Load historical velocity snapshots."""
    if os.path.exists(VELOCITY_FILE):
        try:
            return json.loads(Path(VELOCITY_FILE).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"snapshots": [], "started": None}


def save_velocity_snapshot(progress):
    """Record today's progress as a velocity snapshot."""
    history = load_velocity_history()
    today = datetime.now().strftime("%Y-%m-%d")

    # Don't duplicate if already recorded today
    if history["snapshots"] and history["snapshots"][-1]["date"] == today:
        history["snapshots"][-1] = {
            "date": today,
            "substeps_done": progress["substeps_done"],
            "substeps_total": progress["substeps_total"],
            "phase": progress["phase"],
            "step": progress["step"],
            "phases": progress.get("phases", {}),
        }
    else:
        history["snapshots"].append({
            "date": today,
            "substeps_done": progress["substeps_done"],
            "substeps_total": progress["substeps_total"],
            "phase": progress["phase"],
            "step": progress["step"],
            "phases": progress.get("phases", {}),
        })

    if not history["started"]:
        history["started"] = today

    # Keep last 90 days
    history["snapshots"] = history["snapshots"][-90:]

    os.makedirs(os.path.dirname(VELOCITY_FILE), exist_ok=True)
    Path(VELOCITY_FILE).write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history


def calculate_etas(progress, history):
    """Calculate ETAs for each phase and overall completion."""
    snapshots = history.get("snapshots", [])

    if len(snapshots) < 2:
        # Not enough data yet — return initial estimates
        return {
            "velocity_7d": None,
            "velocity_alltime": None,
            "overall_eta": None,
            "phase_etas": {},
            "confidence": "low",
            "message": "Need at least 2 days of data to calculate velocity.",
        }

    # Calculate velocities over different windows
    def velocity_over(n_days):
        """Substeps per day over the last n_days."""
        if len(snapshots) < 2:
            return None
        recent = [s for s in snapshots if (datetime.now() - datetime.strptime(s["date"], "%Y-%m-%d")).days <= n_days]
        if len(recent) < 2:
            # Fall back to all available data
            recent = snapshots
        if len(recent) < 2:
            return None
        first, last = recent[0], recent[-1]
        days = max((datetime.strptime(last["date"], "%Y-%m-%d") - datetime.strptime(first["date"], "%Y-%m-%d")).days, 1)
        substeps = last["substeps_done"] - first["substeps_done"]
        return substeps / days if days > 0 else None

    v_3d = velocity_over(3)
    v_7d = velocity_over(7)
    v_14d = velocity_over(14)
    v_all = velocity_over(9999)

    # Use weighted average: recent velocity matters more
    # Weight: 3-day (0.5), 7-day (0.3), 14-day (0.15), all-time (0.05)
    velocities = [(v_3d, 0.5), (v_7d, 0.3), (v_14d, 0.15), (v_all, 0.05)]
    valid = [(v, w) for v, w in velocities if v is not None and v > 0]

    if not valid:
        return {
            "velocity_7d": v_7d,
            "velocity_alltime": v_all,
            "overall_eta": None,
            "phase_etas": {},
            "confidence": "low",
            "message": "No measurable progress yet. Velocity is zero.",
        }

    total_weight = sum(w for _, w in valid)
    weighted_velocity = sum(v * w for v, w in valid) / total_weight

    # Confidence based on data points
    n_days_tracked = len(snapshots)
    if n_days_tracked >= 14:
        confidence = "high"
    elif n_days_tracked >= 7:
        confidence = "medium"
    else:
        confidence = "low"

    # Overall ETA
    remaining = progress["substeps_total"] - progress["substeps_done"]
    days_remaining = remaining / weighted_velocity if weighted_velocity > 0 else None
    overall_eta = (datetime.now() + timedelta(days=days_remaining)).strftime("%B %d, %Y") if days_remaining else None

    # Per-phase ETAs
    phase_etas = {}
    phases = progress.get("phases", {})
    cumulative_remaining = 0

    for phase_num in sorted(phases.keys()):
        p = phases[phase_num]
        p_remaining = p["total"] - p["done"]

        if p["done"] == p["total"] and p["total"] > 0:
            # Phase complete
            phase_etas[phase_num] = {
                "status": "complete",
                "done": p["done"],
                "total": p["total"],
                "percent": 100.0,
                "days_remaining": 0,
                "eta": "Done ✅",
            }
        elif p["done"] > 0:
            # Phase in progress — use current velocity
            days_left = p_remaining / weighted_velocity if weighted_velocity > 0 else None
            phase_etas[phase_num] = {
                "status": "in_progress",
                "done": p["done"],
                "total": p["total"],
                "percent": p["percent"],
                "days_remaining": round(days_left, 1) if days_left else None,
                "eta": (datetime.now() + timedelta(days=days_left)).strftime("%b %d") if days_left else "?",
            }
        else:
            # Phase not started — ETA based on cumulative remaining work ahead of it
            cumulative_remaining += p_remaining
            days_until = cumulative_remaining / weighted_velocity if weighted_velocity > 0 else None
            phase_etas[phase_num] = {
                "status": "not_started",
                "done": 0,
                "total": p["total"],
                "percent": 0,
                "days_remaining": round(days_until, 1) if days_until else None,
                "eta": (datetime.now() + timedelta(days=days_until)).strftime("%b %d") if days_until else "?",
            }

    # Velocity trend (is it speeding up or slowing down?)
    trend = None
    if v_3d is not None and v_7d is not None and v_7d > 0:
        ratio = v_3d / v_7d
        if ratio > 1.2:
            trend = "accelerating"
        elif ratio < 0.8:
            trend = "slowing"
        else:
            trend = "steady"

    return {
        "velocity_3d": round(v_3d, 1) if v_3d else None,
        "velocity_7d": round(v_7d, 1) if v_7d else None,
        "velocity_alltime": round(v_all, 1) if v_all else None,
        "weighted_velocity": round(weighted_velocity, 1),
        "overall_days_remaining": round(days_remaining, 1) if days_remaining else None,
        "overall_eta": overall_eta,
        "phase_etas": phase_etas,
        "confidence": confidence,
        "trend": trend,
        "message": None,
    }


def get_recent_sessions(hours=24):
    """Parse log files from the last N hours."""
    log_dir = os.path.join(PROJECT_DIR, ".automation", "logs")
    if not os.path.exists(log_dir):
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    recent_logs = []

    for log_file in sorted(glob.glob(os.path.join(log_dir, "window_*.log")), reverse=True):
        # Parse timestamp from filename: window_20260420_080000.log
        basename = os.path.basename(log_file)
        try:
            ts_str = basename.replace("window_", "").replace(".log", "")
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        except ValueError:
            continue

        if ts < cutoff:
            break

        content = Path(log_file).read_text(encoding="utf-8", errors="replace")

        # Extract key stats from the log
        session_count = 0
        errors = []
        advances = []
        stalls = []

        for line in content.splitlines():
            if "SESSION" in line and "|" in line:
                session_count += 1
            if "Advanced:" in line:
                advances.append(line.split("]")[-1].strip() if "]" in line else line)
            if "error" in line.lower() and "Non-rate-limit" not in line:
                if "STALL" in line or "ERROR" in line or "failed" in line.lower():
                    errors.append(line.split("]")[-1].strip() if "]" in line else line)
            if "STALL" in line:
                stalls.append(line.split("]")[-1].strip() if "]" in line else line)

        # Extract the summary block at the end
        summary_match = re.search(r'Sessions:\s*(\d+).*?Final:.*?Step\s*([\d.]+).*?Duration:\s*(\d+)', content, re.DOTALL)

        recent_logs.append({
            "file": basename,
            "timestamp": ts,
            "sessions": summary_match.group(1) if summary_match else str(session_count),
            "final_step": summary_match.group(2) if summary_match else "?",
            "duration_min": summary_match.group(3) if summary_match else "?",
            "advances": advances,
            "errors": errors,
            "stalls": stalls,
        })

    return recent_logs


def detect_blockers(progress, recent_logs):
    """Identify blockers from progress and logs."""
    blockers = []

    # Check for stalls in progress
    for step_id, status in progress["steps"].items():
        if status == "blocked":
            blockers.append(f"Step {step_id} is marked as BLOCKED in PROGRESS.md")

    # Check for stalls in recent logs
    for log in recent_logs:
        for stall in log["stalls"]:
            blockers.append(f"Stall detected: {stall}")

    # Check for repeated errors
    all_errors = []
    for log in recent_logs:
        all_errors.extend(log["errors"])
    if len(all_errors) >= 3:
        blockers.append(f"{len(all_errors)} errors in the last 24h — may need manual intervention")

    # Check if no sessions ran
    if not recent_logs:
        blockers.append("No automated sessions ran in the last 24 hours — check scheduler")

    return blockers


# ─── Screenshots ────────────────────────────────────────────────────────────

def capture_screenshots():
    """Capture relevant screenshots. Returns list of (filename, bytes) tuples."""
    screenshots = []
    screenshot_dir = os.path.join(PROJECT_DIR, ".automation", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    system = platform.system()

    # 1. Capture full desktop (shows Unity/Blender if open)
    desktop_path = os.path.join(screenshot_dir, "desktop.png")
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["screencapture", "-x", desktop_path], check=True, timeout=10)
        elif system == "Windows":
            # PowerShell screenshot
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            $screen = [System.Windows.Forms.Screen]::PrimaryScreen
            $bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
            $bitmap.Save('{desktop_path}')
            $graphics.Dispose()
            $bitmap.Dispose()
            """
            subprocess.run(["powershell", "-Command", ps_script], check=True, timeout=10)
        elif system == "Linux":
            # Try scrot, then import (ImageMagick), then gnome-screenshot
            for cmd in [
                ["scrot", desktop_path],
                ["import", "-window", "root", desktop_path],
                ["gnome-screenshot", "-f", desktop_path],
            ]:
                try:
                    subprocess.run(cmd, check=True, timeout=10)
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue

        if os.path.exists(desktop_path):
            screenshots.append(("desktop.png", Path(desktop_path).read_bytes()))
    except Exception as e:
        pass  # Screenshot capture is best-effort

    # 2. Pick up any Blender preview renders
    render_dir = os.path.join(PROJECT_DIR, ".automation", "renders")
    if os.path.exists(render_dir):
        cutoff = datetime.now() - timedelta(hours=24)
        for img_path in sorted(glob.glob(os.path.join(render_dir, "*.png")), reverse=True)[:3]:
            mtime = datetime.fromtimestamp(os.path.getmtime(img_path))
            if mtime > cutoff:
                screenshots.append((os.path.basename(img_path), Path(img_path).read_bytes()))

    # 3. Pick up any Unity screenshots (if MCP tool saves them)
    unity_screenshots = os.path.join(PROJECT_DIR, ".automation", "unity-screenshots")
    if os.path.exists(unity_screenshots):
        cutoff = datetime.now() - timedelta(hours=24)
        for img_path in sorted(glob.glob(os.path.join(unity_screenshots, "*.png")), reverse=True)[:3]:
            mtime = datetime.fromtimestamp(os.path.getmtime(img_path))
            if mtime > cutoff:
                screenshots.append((os.path.basename(img_path), Path(img_path).read_bytes()))

    return screenshots


# ─── Git Stats ──────────────────────────────────────────────────────────────

def get_git_stats(hours=24):
    """Get git commit stats from the last N hours."""
    try:
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--stat"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            commit_count = len([l for l in lines if not l.startswith(" ")])

            # Count files changed
            files_changed = set()
            for line in lines:
                match = re.match(r'\s+(.+?)\s+\|\s+\d+', line)
                if match:
                    files_changed.add(match.group(1).strip())

            return {
                "commits": commit_count,
                "files_changed": len(files_changed),
                "summary": "\n".join(lines[:30]),  # First 30 lines
            }
    except Exception:
        pass
    return {"commits": 0, "files_changed": 0, "summary": "No commits"}


# ─── Build Email ────────────────────────────────────────────────────────────

def build_email_html(progress, recent_logs, blockers, git_stats, etas):
    """Build an HTML email body."""

    # Progress bar
    pct = progress["percent"]
    bar_color = "#22c55e" if pct > 75 else "#f59e0b" if pct > 25 else "#6366f1"

    # Blocker section
    if blockers:
        blocker_html = "".join(f'<li style="color:#ef4444;margin:4px 0;">⚠️ {b}</li>' for b in blockers)
        blocker_section = f'<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:16px 0;"><h3 style="margin:0 0 8px;color:#dc2626;">Blockers</h3><ul style="margin:0;padding-left:20px;">{blocker_html}</ul></div>'
    else:
        blocker_section = '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:16px 0;"><p style="margin:0;color:#16a34a;">✅ No blockers — everything running smoothly.</p></div>'

    # ── ETA Section ──
    if etas.get("message"):
        # Not enough data yet
        eta_section = f'''
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin:16px 0;">
            <h3 style="margin:0 0 8px;color:#2563eb;">📊 ETA Estimates</h3>
            <p style="margin:0;color:#3b82f6;">{etas["message"]}</p>
        </div>'''
    else:
        # Build phase ETA table
        phase_names = {"1": "Foundation", "2": "Asset Pipeline", "3": "Game Systems", "4": "Polish & Automation"}
        phase_rows = ""
        for pnum in sorted(etas.get("phase_etas", {}).keys()):
            pe = etas["phase_etas"][pnum]
            name = phase_names.get(pnum, f"Phase {pnum}")

            if pe["status"] == "complete":
                status_badge = '<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:99px;font-size:11px;">DONE</span>'
                eta_str = "✅ Complete"
                bar_pct = 100
                bar_clr = "#22c55e"
            elif pe["status"] == "in_progress":
                status_badge = '<span style="background:#f59e0b;color:white;padding:2px 8px;border-radius:99px;font-size:11px;">IN PROGRESS</span>'
                days = pe["days_remaining"]
                eta_str = f'{pe["eta"]} <span style="color:#6b7280;font-size:12px;">(~{days}d)</span>' if days else "?"
                bar_pct = pe["percent"]
                bar_clr = "#f59e0b"
            else:
                status_badge = '<span style="background:#9ca3af;color:white;padding:2px 8px;border-radius:99px;font-size:11px;">UPCOMING</span>'
                days = pe["days_remaining"]
                eta_str = f'{pe["eta"]} <span style="color:#6b7280;font-size:12px;">(~{days}d)</span>' if days else "?"
                bar_pct = 0
                bar_clr = "#9ca3af"

            phase_rows += f'''
            <tr>
                <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;">
                    <strong>Phase {pnum}</strong><br>
                    <span style="font-size:12px;color:#6b7280;">{name}</span>
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;">{status_badge}</td>
                <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;min-width:120px;">
                    <div style="background:#e5e7eb;border-radius:99px;height:8px;overflow:hidden;margin-bottom:4px;">
                        <div style="background:{bar_clr};height:100%;width:{bar_pct}%;border-radius:99px;"></div>
                    </div>
                    <span style="font-size:12px;color:#6b7280;">{pe["done"]}/{pe["total"]}</span>
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;">{eta_str}</td>
            </tr>'''

        # Velocity display
        v = etas.get("weighted_velocity", 0)
        trend = etas.get("trend")
        trend_icon = {"accelerating": "📈", "slowing": "📉", "steady": "➡️"}.get(trend, "")
        trend_color = {"accelerating": "#22c55e", "slowing": "#ef4444", "steady": "#6b7280"}.get(trend, "#6b7280")
        confidence = etas.get("confidence", "low")
        conf_badge = {"high": "🟢 High", "medium": "🟡 Medium", "low": "🔴 Low"}.get(confidence, confidence)

        overall_eta = etas.get("overall_eta", "?")
        overall_days = etas.get("overall_days_remaining")
        overall_str = f'{overall_eta} <span style="color:#6b7280;">({overall_days} days)</span>' if overall_days else "Calculating..."

        eta_section = f'''
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:20px;margin:16px 0;">
            <h3 style="margin:0 0 4px;color:#1e40af;">📊 Estimated Completion</h3>
            <div style="display:flex;align-items:baseline;gap:8px;margin:8px 0 16px;">
                <span style="font-size:28px;font-weight:bold;color:#1e40af;">{overall_str}</span>
            </div>
            <div style="display:flex;gap:16px;margin-bottom:16px;font-size:13px;">
                <div>
                    <span style="color:#6b7280;">Velocity:</span>
                    <strong>{v}</strong> substeps/day {trend_icon}
                    <span style="color:{trend_color};">{trend or ""}</span>
                </div>
                <div>
                    <span style="color:#6b7280;">Confidence:</span> {conf_badge}
                </div>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <tr style="background:#dbeafe;">
                    <th style="padding:8px;text-align:left;">Phase</th>
                    <th style="padding:8px;text-align:left;">Status</th>
                    <th style="padding:8px;text-align:left;">Progress</th>
                    <th style="padding:8px;text-align:left;">ETA</th>
                </tr>
                {phase_rows}
            </table>
        </div>'''

    # Session summary
    total_sessions = sum(int(l.get("sessions", 0)) for l in recent_logs)
    total_advances = sum(len(l["advances"]) for l in recent_logs)
    window_count = len(recent_logs)

    session_rows = ""
    for log in recent_logs:
        advances_str = "<br>".join(log["advances"][:3]) if log["advances"] else "In progress"
        errors_str = f'<span style="color:#ef4444;">{len(log["errors"])} errors</span>' if log["errors"] else "Clean"
        session_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{log["timestamp"].strftime("%H:%M")}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{log["sessions"]} sessions</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{log["duration_min"]}m</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{advances_str}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{errors_str}</td>
        </tr>"""

    # Step status grid
    step_grid = ""
    for step_id, status in sorted(progress["steps"].items()):
        color = {"done": "#22c55e", "in_progress": "#f59e0b", "blocked": "#ef4444"}.get(status, "#9ca3af")
        emoji = {"done": "✅", "in_progress": "🔨", "blocked": "🚫"}.get(status, "⬜")
        step_grid += f'<span style="display:inline-block;margin:2px;padding:2px 8px;background:{color}20;border:1px solid {color};border-radius:4px;font-size:12px;">{emoji} {step_id}</span> '

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:700px;margin:0 auto;color:#1f2937;">
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);color:white;padding:24px;border-radius:12px 12px 0 0;">
            <h1 style="margin:0;font-size:24px;">🎮 Game Agent Daily Report</h1>
            <p style="margin:8px 0 0;opacity:0.8;">{datetime.now().strftime("%A, %B %d, %Y")}</p>
        </div>

        <div style="background:white;padding:24px;border:1px solid #e5e7eb;border-top:none;">

            <!-- Progress Overview -->
            <div style="margin-bottom:24px;">
                <h2 style="margin:0 0 12px;font-size:18px;">Progress</h2>
                <div style="display:flex;align-items:center;gap:16px;margin-bottom:8px;">
                    <span style="font-size:36px;font-weight:bold;color:{bar_color};">{pct}%</span>
                    <div style="flex:1;">
                        <div style="background:#e5e7eb;border-radius:99px;height:12px;overflow:hidden;">
                            <div style="background:{bar_color};height:100%;width:{pct}%;border-radius:99px;transition:width 0.5s;"></div>
                        </div>
                        <p style="margin:4px 0 0;font-size:13px;color:#6b7280;">{progress["substeps_done"]}/{progress["substeps_total"]} substeps completed</p>
                    </div>
                </div>
                <table style="width:100%;font-size:14px;">
                    <tr><td style="color:#6b7280;padding:2px 8px 2px 0;">Active Phase:</td><td><strong>{progress["phase"]}</strong></td></tr>
                    <tr><td style="color:#6b7280;padding:2px 8px 2px 0;">Active Step:</td><td><strong>{progress["step"]}</strong></td></tr>
                    <tr><td style="color:#6b7280;padding:2px 8px 2px 0;">Next Action:</td><td>{progress["next_action"]}</td></tr>
                </table>
            </div>

            {blocker_section}

            {eta_section}

            <!-- Last 24h Stats -->
            <div style="display:flex;gap:12px;margin:16px 0;">
                <div style="flex:1;background:#f9fafb;border-radius:8px;padding:16px;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#4f46e5;">{window_count}</div>
                    <div style="font-size:12px;color:#6b7280;">Windows</div>
                </div>
                <div style="flex:1;background:#f9fafb;border-radius:8px;padding:16px;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#4f46e5;">{total_sessions}</div>
                    <div style="font-size:12px;color:#6b7280;">Sessions</div>
                </div>
                <div style="flex:1;background:#f9fafb;border-radius:8px;padding:16px;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#4f46e5;">{git_stats["commits"]}</div>
                    <div style="font-size:12px;color:#6b7280;">Commits</div>
                </div>
                <div style="flex:1;background:#f9fafb;border-radius:8px;padding:16px;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#4f46e5;">{git_stats["files_changed"]}</div>
                    <div style="font-size:12px;color:#6b7280;">Files Changed</div>
                </div>
            </div>

            <!-- Window Details -->
            {"" if not session_rows else f'''
            <h3 style="margin:24px 0 8px;font-size:16px;">Window Activity (Last 24h)</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <tr style="background:#f9fafb;">
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb;">Time</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb;">Sessions</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb;">Duration</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb;">Progress</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb;">Health</th>
                </tr>
                {session_rows}
            </table>
            '''}

            <!-- Step Map -->
            <h3 style="margin:24px 0 8px;font-size:16px;">Step Status Map</h3>
            <div style="line-height:2;">{step_grid if step_grid else '<span style="color:#9ca3af;">No steps started yet</span>'}</div>

            <!-- Recent Git Activity -->
            {"" if git_stats["commits"] == 0 else f'''
            <h3 style="margin:24px 0 8px;font-size:16px;">Recent Commits</h3>
            <pre style="background:#1f2937;color:#e5e7eb;padding:16px;border-radius:8px;font-size:12px;overflow-x:auto;white-space:pre-wrap;">{git_stats["summary"][:2000]}</pre>
            '''}

        </div>

        <div style="background:#f9fafb;padding:16px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;text-align:center;font-size:12px;color:#9ca3af;">
            Game Agent System — Automated Build Report<br>
            Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    """
    return html


# ─── Send Email ─────────────────────────────────────────────────────────────

def send_email(html_body, screenshots):
    """Send the report email with embedded screenshots."""
    if not SMTP_USER or not SMTP_PASS:
        print("ERROR: SMTP_USER and SMTP_PASS environment variables must be set.")
        print("  export SMTP_USER='your-email@gmail.com'")
        print("  export SMTP_PASS='your-app-password'")
        print("")
        print("For Gmail, create an App Password at:")
        print("  https://myaccount.google.com/apppasswords")
        sys.exit(1)

    msg = MIMEMultipart("related")
    msg["Subject"] = f"{EMAIL_SUBJECT_PREFIX} Daily Report — {datetime.now().strftime('%b %d')}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO

    # Attach HTML body
    # Add screenshot references to HTML if we have any
    screenshot_html = ""
    if screenshots:
        screenshot_html = '<h3 style="margin:24px 0 8px;font-size:16px;">Screenshots</h3>'
        for i, (filename, _) in enumerate(screenshots):
            screenshot_html += f'''
            <div style="margin:8px 0;">
                <p style="font-size:12px;color:#6b7280;margin:0 0 4px;">{filename}</p>
                <img src="cid:screenshot_{i}" style="max-width:100%;border-radius:8px;border:1px solid #e5e7eb;" />
            </div>'''

    # Insert screenshots before the closing divs
    if screenshot_html:
        html_body = html_body.replace("</div>\n\n        <div style=\"background:#f9fafb",
                                       f"{screenshot_html}</div>\n\n        <div style=\"background:#f9fafb")

    msg.attach(MIMEText(html_body, "html"))

    # Attach screenshot images
    for i, (filename, img_bytes) in enumerate(screenshots):
        img = MIMEImage(img_bytes, name=filename)
        img.add_header("Content-ID", f"<screenshot_{i}>")
        img.add_header("Content-Disposition", "inline", filename=filename)
        msg.attach(img)

    # Send
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"Report sent to {EMAIL_TO}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Save HTML locally as fallback
        fallback = os.path.join(PROJECT_DIR, ".automation", "logs", f"report_{datetime.now().strftime('%Y%m%d')}.html")
        Path(fallback).write_text(html_body, encoding="utf-8")
        print(f"Saved HTML report to {fallback}")


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print(f"Generating daily report for {PROJECT_DIR}...")

    progress = parse_progress()
    recent_logs = get_recent_sessions(hours=24)
    blockers = detect_blockers(progress, recent_logs)
    git_stats = get_git_stats(hours=24)
    screenshots = capture_screenshots()

    # Velocity tracking — save today's snapshot and calculate ETAs
    history = save_velocity_snapshot(progress)
    etas = calculate_etas(progress, history)

    print(f"  Progress: {progress['percent']}% ({progress['substeps_done']}/{progress['substeps_total']})")
    print(f"  Windows (24h): {len(recent_logs)}")
    print(f"  Blockers: {len(blockers)}")
    print(f"  Screenshots: {len(screenshots)}")
    print(f"  Commits: {git_stats['commits']}")
    if etas.get("weighted_velocity"):
        print(f"  Velocity: {etas['weighted_velocity']} substeps/day ({etas.get('trend', '?')})")
        print(f"  Overall ETA: {etas.get('overall_eta', '?')} ({etas.get('overall_days_remaining', '?')} days)")
    else:
        print(f"  Velocity: {etas.get('message', 'Not enough data')}")

    html = build_email_html(progress, recent_logs, blockers, git_stats, etas)
    send_email(html, screenshots)

    # Post to Slack (primary channel)
    try:
        from slack import send_daily_report as slack_daily
        slack_daily(progress, etas, blockers, git_stats, recent_logs)
        print("  Slack report posted")
    except ImportError:
        # slack.py might not be importable — try calling it directly
        import subprocess
        # The daily report function is complex, so we import it
        pass
    except Exception as e:
        print(f"  Slack report failed: {e}")


if __name__ == "__main__":
    main()
