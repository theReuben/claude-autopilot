#!/usr/bin/env python3
"""
Claude Autopilot — Hands-free automation for Claude Code projects.

Usage:
  autopilot init                     Scaffold a new project from autopilot.yaml
  autopilot run                      Drain the token window (default behavior)
  autopilot run --once               Run a single session
  autopilot run --dry-run            Preview what would happen
  autopilot status                   Show current progress
  autopilot report                   Send daily report (Slack + email)
  autopilot gate <phase>             Run phase gate validation
  autopilot health [pre|post|fix]    Run health checks
  autopilot setup-slack              Interactive Slack setup guide
  autopilot test-slack               Send test messages to Slack
"""

import os
import re
import sys
import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from datetime import datetime, timedelta

# ─── Config Loading ─────────────────────────────────────────────────────────

def find_project_root():
    """Walk up from CWD to find autopilot.yaml."""
    d = Path.cwd()
    while d != d.parent:
        if (d / "autopilot.yaml").exists():
            return d
        d = d.parent
    return Path.cwd()


def load_config(project_dir=None):
    """Load autopilot.yaml and return parsed config."""
    if project_dir is None:
        project_dir = find_project_root()
    config_path = Path(project_dir) / "autopilot.yaml"
    if not config_path.exists():
        print(f"No autopilot.yaml found in {project_dir}")
        print("Run 'autopilot init' to create one, or copy autopilot.example.yaml")
        sys.exit(1)
    try:
        # Use PyYAML if available, otherwise basic parsing
        import yaml
        return yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except ImportError:
        print("PyYAML required: pip install pyyaml")
        sys.exit(1)

PROJECT_DIR = find_project_root()

# ─── Init Command ───────────────────────────────────────────────────────────

def cmd_init():
    """Scaffold a project from autopilot.yaml."""
    config = load_config(PROJECT_DIR)
    project_name = config.get("project", {}).get("name", "My Project")
    phases = config.get("phases", [])
    knowledge = config.get("knowledge", {})
    ignore_patterns = config.get("ignore", [])
    protected = config.get("protected_files", [])
    review_cfg = config.get("review", {})

    print(f"Initializing project: {project_name}")
    print(f"Phases: {len(phases)}")

    # ── Create directories ──
    dirs = [
        ".automation/logs",
        ".automation/backups",
        "docs",
    ]
    for d in dirs:
        (PROJECT_DIR / d).mkdir(parents=True, exist_ok=True)
        print(f"  📁 {d}/")

    # ── Generate PROGRESS.md ──
    progress = generate_progress_md(config)
    write_if_new(PROJECT_DIR / "PROGRESS.md", progress)

    # ── Generate CLAUDE.md ──
    claude_md = generate_claude_md(config)
    write_if_new(PROJECT_DIR / "CLAUDE.md", claude_md)

    # ── Generate MASTER_PLAN.md ──
    master = generate_master_plan(config)
    write_if_new(PROJECT_DIR / "MASTER_PLAN.md", master)

    # ── Generate FEEDBACK.md ──
    feedback = generate_feedback_md(config)
    write_if_new(PROJECT_DIR / "FEEDBACK.md", feedback)

    # ── Generate .claudeignore ──
    claudeignore = "\n".join(ignore_patterns) + "\n.automation/\n"
    write_if_new(PROJECT_DIR / ".claudeignore", claudeignore)

    # ── Generate docs/cookbook.md ──
    cookbook_path = PROJECT_DIR / (knowledge.get("cookbook", "docs/cookbook.md"))
    write_if_new(cookbook_path, "# Cookbook — Known Issues & Solutions\n\nAdd non-obvious bug fixes and workarounds here as you discover them.\n\n---\n\n")

    # ── Generate docs/decisions.md ──
    decisions_path = PROJECT_DIR / (knowledge.get("decisions", "docs/decisions.md"))
    write_if_new(decisions_path, textwrap.dedent("""\
        # Architecture Decision Records

        Claude: check this file before making significant technical decisions.
        Do NOT contradict existing ADRs without explicitly superseding them.

        Format:
        ## ADR-NNN: Title
        **Date:** YYYY-MM-DD | **Status:** accepted
        **Context:** Why | **Decision:** What | **Consequences:** Impact

        ---
    """))

    # ── Generate docs/asset-manifest.json ──
    manifest = {"projectName": project_name, "currentPhase": 1, "lastUpdated": ""}
    write_if_new(PROJECT_DIR / "docs" / "asset-manifest.json",
                 json.dumps(manifest, indent=2))

    # ── Copy autopilot scripts ──
    script_dir = Path(__file__).parent
    for script in ["slack.py", "daily-report.py", "healthcheck.py", "slack-app-manifest.yaml"]:
        src = script_dir / script
        if src.exists():
            dst = PROJECT_DIR / script
            if not dst.exists():
                shutil.copy2(src, dst)
                print(f"  📄 {script}")

    print(f"\n✅ Project scaffolded. Next steps:")
    print(f"  1. Edit CLAUDE.md with your project-specific conventions")
    print(f"  2. Edit MASTER_PLAN.md with detailed step instructions")
    print(f"  3. Add API references to docs/api-reference/")
    print(f"  4. Set up Slack: autopilot setup-slack")
    print(f"  5. Start building: autopilot run")


def write_if_new(path, content):
    """Write file only if it doesn't exist (don't overwrite user edits)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  ⏭ {path.name} (already exists, skipping)")
    else:
        path.write_text(content, encoding="utf-8")
        print(f"  📄 {path.name}")


# ─── Generators ─────────────────────────────────────────────────────────────

def generate_progress_md(config):
    """Generate PROGRESS.md from config phases."""
    phases = config.get("phases", [])
    project_name = config.get("project", {}).get("name", "My Project")

    lines = [
        "# PROGRESS TRACKER",
        f"# Project: {project_name}",
        "# ================",
        "# Claude Code: UPDATE THIS FILE after completing each step.",
        "# At the start of every session, READ THIS FILE FIRST.",
        "#",
        "# Status values: not_started | in_progress | blocked | done",
        "",
        "## Current State",
        "- **Active Phase:** 1",
        f"- **Active Step:** {phases[0]['steps'][0]['id'] if phases and phases[0].get('steps') else '1.1'}",
        "- **Last Session Summary:** (not started)",
        f"- **Next Action:** Begin Step {phases[0]['steps'][0]['id'] if phases and phases[0].get('steps') else '1.1'}",
        "",
        "---",
        "",
    ]

    for i, phase in enumerate(phases, 1):
        lines.append(f"## Phase {i}: {phase['name']}")
        lines.append("")
        for step in phase.get("steps", []):
            lines.append(f"### Step {step['id']}: {step['name']}")
            lines.append(f"- **Status:** not_started")
            lines.append(f"- **Substeps:**")
            for substep in step.get("substeps", []):
                lines.append(f"  - [ ] {substep}")
            lines.append(f"- **Notes:**")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## Session Log",
        "",
        "| Session # | Date | Phase.Step | What was done | What's next | Issues hit |",
        "|---|---|---|---|---|---|",
        "| 1 | | | | | |",
    ])

    return "\n".join(lines) + "\n"


def generate_claude_md(config):
    """Generate CLAUDE.md from config."""
    project = config.get("project", {})
    review_cfg = config.get("review", {})
    knowledge = config.get("knowledge", {})
    phases = config.get("phases", [])

    review_notice = ""
    if review_cfg.get("enabled"):
        reviewer = review_cfg.get("reviewer", "a reviewer")
        msg = review_cfg.get("message", "").format(reviewer=reviewer)
        review_notice = f"""
### IMPORTANT: Your Work Will Be Audited
{msg}
Write code as if a senior engineer is reviewing every line. No shortcuts,
no placeholder implementations marked as done, no "this should work"
without testing. If uncertain, add a TODO comment and note in PROGRESS.md.
"""

    ref_lines = ""
    for ref in knowledge.get("references", []):
        ref_lines += f"- `{ref['path']}` — {ref.get('description', '')}\n"

    template_lines = ""
    for tmpl in knowledge.get("templates", []):
        template_lines += f"- `{tmpl['path']}` — {tmpl.get('description', '')}\n"

    phase_summary = ""
    for i, phase in enumerate(phases, 1):
        last_step = phase["steps"][-1]["id"] if phase.get("steps") else "?"
        phase_summary += f"### Phase {i}: {phase['name']}\n{phase.get('description', '')}\n"
        phase_summary += f"Steps: {phase['steps'][0]['id']}–{last_step}\n\n"

    return textwrap.dedent(f"""\
        # {project.get('name', 'Project')}

        {project.get('description', '')}

        ## Session Management
        {review_notice}
        ### Starting a Session (DO THIS EVERY TIME)
        1. Read `PROGRESS.md` FIRST — find the current step and what happened last session
        2. Read `FEEDBACK.md` — handle every [UNREAD] item before other work. Change to [READ].
        3. Read this file (`CLAUDE.md`) for conventions
        4. Read the relevant API reference for your current task
        5. Read `{knowledge.get('cookbook', 'docs/cookbook.md')}` before debugging
        6. Check `{knowledge.get('decisions', 'docs/decisions.md')}` before architectural decisions
        7. Start from templates when creating new files
        8. Work autonomously — do NOT ask questions

        ### Ending a Session (DO THIS BEFORE STOPPING)
        1. Update `PROGRESS.md` — check off substeps, update Active Step and Next Action, add Session Log row
        2. Update `{knowledge.get('cookbook', 'docs/cookbook.md')}` with any discoveries
        3. Update `{knowledge.get('decisions', 'docs/decisions.md')}` if you made architectural decisions
        4. Commit all changes

        ### Feedback Loop
        The human may leave notes in `FEEDBACK.md` (synced from Slack).
        Items tagged [UNREAD] are top priority. If one says STOP, halt that work immediately.

        ## Knowledge Base

        ### API References
        {ref_lines if ref_lines else '(Add references to docs/api-reference/)'}

        ### Templates
        {template_lines if template_lines else '(Add templates to docs/patterns/)'}

        ### Cookbook
        `{knowledge.get('cookbook', 'docs/cookbook.md')}` — read before debugging

        ### Architecture Decisions
        `{knowledge.get('decisions', 'docs/decisions.md')}` — check before making decisions

        ## Build Phases

        {phase_summary}

        ## Code Conventions

        (Add your project-specific conventions here)

        ## Known Gotchas

        (Add project-specific gotchas here)
    """)


def generate_master_plan(config):
    """Generate MASTER_PLAN.md from config."""
    project = config.get("project", {})
    phases = config.get("phases", [])
    knowledge = config.get("knowledge", {})

    lines = [
        f"# MASTER PLAN — {project.get('name', 'Project')}",
        "",
        "## Instructions for Claude Code",
        "",
        "**FIRST: Read `PROGRESS.md`** to find out where the project is.",
        "- If first session, everything is `not_started` — begin at Phase 1.",
        "- If continuing, find the `Active Step` and `Next Action` and resume.",
        "",
        "**LAST: Update `PROGRESS.md`** before the session ends.",
        "- Check off completed substeps, update Active Step/Next Action, add Session Log row.",
        "",
        "Work autonomously. If ambiguous, pick the most reasonable interpretation.",
        "",
        "Before starting any task:",
        "1. Read `PROGRESS.md`",
        "2. Read `FEEDBACK.md` — handle [UNREAD] items first",
        "3. Read `CLAUDE.md`",
        "4. Read relevant API reference docs",
        f"5. Read `{knowledge.get('cookbook', 'docs/cookbook.md')}`",
        "6. Start from templates when creating new files",
        "",
        "After completing any task:",
        "1. Test it if possible",
        "2. Update `PROGRESS.md`",
        f"3. Update `{knowledge.get('cookbook', 'docs/cookbook.md')}` with discoveries",
        "4. Commit with a descriptive message",
        "",
        "If running low on context:",
        "1. IMMEDIATELY update `PROGRESS.md`",
        "2. Add Session Log entry",
        "3. Commit",
        "",
        "---",
        "",
    ]

    for i, phase in enumerate(phases, 1):
        lines.append(f"## Phase {i}: {phase['name']}")
        lines.append("")
        if phase.get("description"):
            lines.append(phase["description"])
            lines.append("")
        for step in phase.get("steps", []):
            lines.append(f"### Step {step['id']}: {step['name']}")
            lines.append("")
            lines.append("Substeps:")
            for substep in step.get("substeps", []):
                lines.append(f"- {substep}")
            lines.append("")
            lines.append("(Add detailed instructions for this step here)")
            lines.append("")

        # Gate info
        gate = phase.get("gate", {})
        if gate:
            lines.append(f"### Phase {i} Gate")
            lines.append(f"After completing the last step, run: `autopilot gate {i}`")
            if gate.get("required_files"):
                lines.append("Required files: " + ", ".join(f"`{f}`" for f in gate["required_files"]))
            if gate.get("checks"):
                lines.append("Checks: " + ", ".join(f"`{c}`" for c in gate["checks"]))
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines) + "\n"


def generate_feedback_md(config):
    """Generate FEEDBACK.md."""
    slack_enabled = config.get("slack", {}).get("enabled", False)
    source_note = (
        "This file is populated automatically from the #feedback Slack channel.\n"
        "The human posts in Slack → slack.py syncs messages here before each session.\n"
        if slack_enabled else
        "The human edits this file directly to give Claude feedback.\n"
    )

    return textwrap.dedent(f"""\
        # FEEDBACK — Human-in-the-Loop Notes

        Claude: READ THIS FILE at the start of every session, right after PROGRESS.md.
        Address every item marked [UNREAD] before doing anything else.
        After addressing an item, change its tag to [READ] and note what you did.

        If this file is empty below the line, there's no feedback — proceed normally.

        {source_note}
        ---
    """)


# ─── Run Command ────────────────────────────────────────────────────────────

def cmd_run(once=False, dry_run=False):
    """Run automated sessions. Delegates to run-session.sh."""
    config = load_config(PROJECT_DIR)

    # Generate the run script dynamically from config
    script = generate_run_script(config)
    script_path = PROJECT_DIR / ".automation" / "run-session.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    os.chmod(script_path, 0o755)

    args = [str(script_path)]
    if once:
        args.append("--once")
    elif dry_run:
        args.append("--dry-run")

    os.environ["GAME_AGENT_PROJECT_DIR"] = str(PROJECT_DIR)
    os.execvp("bash", ["bash"] + args)


def generate_run_script(config):
    """Generate run-session.sh from config."""
    session = config.get("session", {})
    phases = config.get("phases", [])
    models = config.get("models", {})
    review_cfg = config.get("review", {})
    knowledge = config.get("knowledge", {})
    slack_cfg = config.get("slack", {})

    max_turns = session.get("max_turns", 75)
    permission_mode = session.get("permission_mode", "auto")
    inter_pause = session.get("inter_session_pause", 10)
    window_duration = session.get("window_duration", 19200)
    stall_threshold = session.get("stall_threshold", 5)
    default_model = models.get("default", "sonnet")

    # Build opus steps list from config
    opus_steps = []
    for phase in phases:
        for step in phase.get("steps", []):
            if step.get("model", default_model) == "opus":
                opus_steps.append(step["id"])
    opus_steps_str = " ".join(opus_steps) if opus_steps else ""

    # Build last-step-per-phase map for gate triggers
    gate_cases = ""
    for i, phase in enumerate(phases, 1):
        steps = phase.get("steps", [])
        if steps and phase.get("gate"):
            last_step = steps[-1]["id"]
            gate_cases += f"""
                {last_step})
                    log "Phase {i} final step complete — running gate..."
                    if python3 "$PROJECT_DIR/autopilot.py" gate {i} 2>&1 | tee -a "$LOG_FILE"; then
                        python3 "$PROJECT_DIR/slack.py" alert gate_passed {i} 2>/dev/null || true
                        python3 "$PROJECT_DIR/slack.py" alert phase_complete {i} 2>/dev/null || true
                        git tag -f "phase-{i}-complete" 2>/dev/null || true
                    else
                        python3 "$PROJECT_DIR/slack.py" alert gate_failed {i} 2>/dev/null || true
                    fi ;;"""

    # Review notice for prompt
    review_notice = ""
    if review_cfg.get("enabled"):
        reviewer = review_cfg.get("reviewer", "a reviewer")
        review_notice = f"QUALITY NOTICE: Your code WILL be reviewed by {reviewer} after each phase. Do not cut corners."

    cookbook = knowledge.get("cookbook", "docs/cookbook.md")
    decisions = knowledge.get("decisions", "docs/decisions.md")

    # Slack notifications
    slack_session_start = 'python3 "$PROJECT_DIR/slack.py" session-start "$SESSION_COUNT" "$phase" "$step" "$model" "$(( $(seconds_remaining) / 60 ))" 2>/dev/null || true' if slack_cfg.get("notify_session_start", True) else ""
    slack_session_end = 'python3 "$PROJECT_DIR/slack.py" session-end "$SESSION_COUNT" "$phase" "$step" "$new_step" 2>/dev/null || true' if slack_cfg.get("notify_session_end", True) else ""
    slack_feedback_sync = 'python3 "$PROJECT_DIR/slack.py" sync-feedback 2>&1 | tee -a "$LOG_FILE" || true' if slack_cfg.get("enabled", False) else ""

    return textwrap.dedent(f"""\
        #!/bin/bash
        set -euo pipefail
        PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
        LOG_DIR="$PROJECT_DIR/.automation/logs"
        MAX_TURNS={max_turns}
        PERMISSION_MODE="{permission_mode}"
        INTER_SESSION_PAUSE={inter_pause}
        RATE_LIMIT_PAUSE=60
        MAX_RATE_LIMIT_RETRIES=5
        WINDOW_DURATION_SECONDS={window_duration}
        STALL_THRESHOLD={stall_threshold}
        DEFAULT_MODEL="{default_model}"
        OPUS_STEPS="{opus_steps_str}"

        mkdir -p "$LOG_DIR"
        RUN_ID=$(date '+%Y%m%d_%H%M%S')
        LOG_FILE="$LOG_DIR/window_${{RUN_ID}}.log"
        WINDOW_START=$(date +%s)
        SESSION_COUNT=0
        CONSECUTIVE_SAME_STEP=0
        LAST_STEP=""

        log() {{ echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }}

        get_current_step() {{ grep "^\\- \\*\\*Active Step:\\*\\*" "$PROJECT_DIR/PROGRESS.md" 2>/dev/null | sed 's/.*Active Step:\\*\\* //' | tr -d ' ' || echo "1.1"; }}
        get_current_phase() {{ grep "^\\- \\*\\*Active Phase:\\*\\*" "$PROJECT_DIR/PROGRESS.md" 2>/dev/null | sed 's/.*Active Phase:\\*\\* //' | tr -d ' ' || echo "1"; }}
        get_next_action() {{ grep "^\\- \\*\\*Next Action:\\*\\*" "$PROJECT_DIR/PROGRESS.md" 2>/dev/null | sed 's/.*Next Action:\\*\\* //' || echo "Begin"; }}
        is_project_complete() {{ grep -q "Active Step.*done\\|Active Step.*complete" "$PROJECT_DIR/PROGRESS.md" 2>/dev/null && echo "true" || echo "false"; }}
        seconds_remaining() {{ echo $(( WINDOW_DURATION_SECONDS - ($(date +%s) - WINDOW_START) )); }}
        select_model() {{ local s="$1"; for o in $OPUS_STEPS; do [[ "$s" == "$o" ]] && {{ echo "opus"; return; }}; done; echo "$DEFAULT_MODEL"; }}

        check_stall() {{
            local step="$1"
            if [[ "$step" == "$LAST_STEP" ]]; then CONSECUTIVE_SAME_STEP=$((CONSECUTIVE_SAME_STEP + 1))
            else CONSECUTIVE_SAME_STEP=0; fi
            LAST_STEP="$step"
            [[ $CONSECUTIVE_SAME_STEP -lt $STALL_THRESHOLD ]]
        }}

        build_prompt() {{
            local step="$1" next_action="$2"
            local remaining_min=$(( $(seconds_remaining) / 60 ))
            cat <<PROMPT
        You are continuing autonomous work on this project.

        {review_notice}

        INSTRUCTIONS:
        1. Read PROGRESS.md FIRST — find where you left off.
        2. Read FEEDBACK.md — handle every [UNREAD] item first. Change to [READ].
        3. Read CLAUDE.md for conventions.
        4. Read relevant docs for your current task.
        5. Read {cookbook} before debugging.
        6. Check {decisions} before architectural decisions.
        7. Work autonomously — do NOT ask questions.
        8. MAXIMIZE OUTPUT — complete as many substeps as possible.

        CURRENT STATE:
        - Active Step: ${{step}}
        - Next Action: ${{next_action}}
        - Window remaining: ~${{remaining_min}} minutes
        - Session number: $((SESSION_COUNT + 1))

        EXECUTION:
        - Jump into coding after reading docs. Don't over-plan.
        - If you finish a step, immediately start the next.
        - Only mark [x] if verified (parses, correct structure, tested if possible).
        - Record architectural decisions in {decisions}.
        - Record fixes in {cookbook}.

        BEFORE FINAL TURN:
        - Update PROGRESS.md (substeps, Active Step, Next Action, Session Log row).
        - git add -A && git commit -m "descriptive message"

        Begin now. Go fast.
        PROMPT
        }}

        run_single_session() {{
            local step=$(get_current_step) phase=$(get_current_phase)
            local next_action=$(get_next_action) model=$(select_model "$step")
            SESSION_COUNT=$((SESSION_COUNT + 1))
            log "── SESSION $SESSION_COUNT | Phase $phase Step $step | $model | ~$(( $(seconds_remaining) / 60 ))m ──"
            [[ "$(is_project_complete)" == "true" ]] && {{ log "✓ COMPLETE"; return 3; }}
            check_stall "$step" || {{ log "⚠ STALLED"; return 4; }}

            {slack_feedback_sync}
            {slack_session_start}

            if [[ -f "$PROJECT_DIR/healthcheck.py" ]]; then
                python3 "$PROJECT_DIR/healthcheck.py" pre 2>&1 | tee -a "$LOG_FILE"
                if [[ $? -eq 2 ]]; then
                    python3 "$PROJECT_DIR/healthcheck.py" fix 2>&1 | tee -a "$LOG_FILE"
                    python3 "$PROJECT_DIR/healthcheck.py" pre 2>&1 | tee -a "$LOG_FILE"
                    [[ $? -eq 2 ]] && {{ log "Pre-flight failed."; return 1; }}
                fi
            fi

            mkdir -p "$PROJECT_DIR/.automation/backups"
            for f in PROGRESS.md CLAUDE.md {cookbook}; do
                [[ -f "$PROJECT_DIR/$f" ]] && cp "$PROJECT_DIR/$f" "$PROJECT_DIR/.automation/backups/$(basename $f).bak"
            done

            local prompt=$(build_prompt "$step" "$next_action")
            local rate_pause=$RATE_LIMIT_PAUSE
            for attempt in $(seq 1 $MAX_RATE_LIMIT_RETRIES); do
                local exit_code=0
                cd "$PROJECT_DIR"
                claude -p "$prompt" --model "$model" --permission-mode "$PERMISSION_MODE" --max-turns "$MAX_TURNS" --output-format text 2>&1 | tee -a "$LOG_FILE" || exit_code=$?
                if [[ $exit_code -eq 0 ]]; then
                    local new_step=$(get_current_step)
                    [[ "$new_step" != "$step" ]] && log "✓ Advanced: $step → $new_step" || log "→ Still on $step"
                    cd "$PROJECT_DIR"
                    [[ -n $(git status --porcelain 2>/dev/null) ]] && git add -A && git commit -m "Auto #$SESSION_COUNT: Phase $phase Step $step [$(date '+%H:%M')]" 2>/dev/null || true
                    [[ -f "$PROJECT_DIR/healthcheck.py" ]] && python3 "$PROJECT_DIR/healthcheck.py" post 2>&1 | tee -a "$LOG_FILE" || true
                    {slack_session_end}
                    return 0
                fi
                if tail -30 "$LOG_FILE" | grep -qi "rate.limit\\|too many requests\\|429\\|usage.limit"; then
                    [[ $attempt -lt $MAX_RATE_LIMIT_RETRIES ]] && {{ log "Rate limited ($attempt). Waiting ${{rate_pause}}s..."; sleep "$rate_pause"; rate_pause=$((rate_pause * 2)); }} || {{ log "Window exhausted."; return 2; }}
                else
                    log "Error (exit $exit_code)"; return 1
                fi
            done
            return 2
        }}

        drain_window() {{
            log "╔══ AUTOPILOT — DRAINING WINDOW ══╗"
            local consecutive_errors=0
            while true; do
                [[ $(seconds_remaining) -le 0 ]] && {{ log "Window expired."; break; }}
                local result=0
                run_single_session || result=$?
                case $result in
                    0) consecutive_errors=0; sleep "$INTER_SESSION_PAUSE" ;;
                    1) consecutive_errors=$((consecutive_errors + 1))
                       [[ $consecutive_errors -ge 3 ]] && {{ log "3 errors."; python3 "$PROJECT_DIR/slack.py" alert error "3 consecutive errors" 2>/dev/null || true; break; }}
                       sleep 60 ;;
                    2) break ;;
                    3) python3 "$PROJECT_DIR/slack.py" alert project_complete 2>/dev/null || true; break ;;
                    4) python3 "$PROJECT_DIR/slack.py" alert stall "$(get_current_step)" 2>/dev/null || true; break ;;
                esac
                local current=$(get_current_step)
                if [[ "$current" != "$LAST_STEP" && -n "$LAST_STEP" ]]; then
                    cd "$PROJECT_DIR"
                    git tag -f "checkpoint/step-${{LAST_STEP}}" 2>/dev/null || true
                    case "$LAST_STEP" in{gate_cases}
                    esac
                fi
            done
            log "Sessions: $SESSION_COUNT | Final: Phase $(get_current_phase) Step $(get_current_step) | Duration: $(( ($(date +%s) - WINDOW_START) / 60 ))m"
            python3 "$PROJECT_DIR/slack.py" window-summary "$SESSION_COUNT" "$(get_current_step)" "$(( ($(date +%s) - WINDOW_START) / 60 ))" "$(get_current_phase)" 2>/dev/null || true
        }}

        case "${{1:-}}" in
            --once) run_single_session ;;
            --dry-run) echo "Phase $(get_current_phase) | Step $(get_current_step) | Model: $(select_model $(get_current_step))"; echo "Next: $(get_next_action)"; echo ""; build_prompt "$(get_current_step)" "$(get_next_action)" ;;
            --status) echo "Phase $(get_current_phase) | Step $(get_current_step) | Next: $(get_next_action)" ;;
            *) drain_window ;;
        esac
    """)


# ─── Gate Command ───────────────────────────────────────────────────────────

def cmd_gate(phase_num):
    """Run phase gate validation."""
    config = load_config(PROJECT_DIR)
    phases = config.get("phases", [])

    idx = int(phase_num) - 1
    if idx < 0 or idx >= len(phases):
        print(f"Phase {phase_num} not found. Available: 1–{len(phases)}")
        sys.exit(1)

    phase = phases[idx]
    gate = phase.get("gate", {})
    if not gate:
        print(f"No gate defined for Phase {phase_num}. Passing by default.")
        sys.exit(0)

    print(f"\n═══ PHASE {phase_num} GATE: {phase['name']} ═══\n")
    failures = []

    # Check required files
    for f in gate.get("required_files", []):
        path = PROJECT_DIR / f
        if path.exists():
            print(f"  ✅ {f}")
        else:
            print(f"  ❌ {f} — not found")
            failures.append(f)

    # Run check commands
    for cmd in gate.get("checks", []):
        print(f"\n  Running: {cmd}")
        result = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR,
                                capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"  ✅ {cmd}")
        else:
            print(f"  ❌ {cmd}")
            if result.stderr:
                print(f"     {result.stderr[:500]}")
            failures.append(cmd)

    print(f"\n{'═'*50}")
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for f in failures:
            print(f"  ❌ {f}")
        sys.exit(1)
    else:
        print(f"✅ Phase {phase_num} gate PASSED")
        sys.exit(0)


# ─── Status Command ─────────────────────────────────────────────────────────

def cmd_status():
    """Show current project status."""
    progress = PROJECT_DIR / "PROGRESS.md"
    if not progress.exists():
        print("No PROGRESS.md found. Run 'autopilot init' first.")
        return

    content = progress.read_text(encoding="utf-8")
    phase = re.search(r'\*\*Active Phase:\*\*\s*(.+)', content)
    step = re.search(r'\*\*Active Step:\*\*\s*(.+)', content)
    next_action = re.search(r'\*\*Next Action:\*\*\s*(.+)', content)
    done = len(re.findall(r'\[x\]', content, re.IGNORECASE))
    total = len(re.findall(r'\[[ x]\]', content, re.IGNORECASE))
    pct = round(done / total * 100, 1) if total > 0 else 0

    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = f"[{'█' * filled}{'░' * (bar_width - filled)}] {pct}%"

    print(f"\n  {bar}  ({done}/{total} substeps)")
    print(f"  Phase: {phase.group(1).strip() if phase else '?'}")
    print(f"  Step:  {step.group(1).strip() if step else '?'}")
    print(f"  Next:  {next_action.group(1).strip() if next_action else '?'}\n")


# ─── Setup Slack ─────────────────────────────────────────────────────────────

def cmd_setup_slack():
    """Interactive Slack setup guide."""
    print("""
╔══════════════════════════════════════════════════╗
║         Slack Setup for Claude Autopilot         ║
╚══════════════════════════════════════════════════╝

Step 1: Create the Slack App
  → Go to https://api.slack.com/apps
  → Click "Create New App" → "From an app manifest"
  → Pick your workspace
  → Paste the contents of slack-app-manifest.yaml
  → Click Next → Create

Step 2: Install to Workspace
  → In the left sidebar, click "Install App"
  → Click "Install to Workspace" → Allow
  → Copy the "Bot User OAuth Token" (starts with xoxb-)

Step 3: Create Channels
  → In Slack, create 3 channels:
    • #game-agent-progress  (or your preferred name)
    • #game-agent-alerts
    • #game-agent-feedback
  → In each channel, type: /invite @Game Agent

Step 4: Get Channel IDs
  → Right-click each channel → "View channel details"
  → Copy the Channel ID at the bottom of the popup

Step 5: Set Environment Variables
  Add these to your shell profile (~/.bashrc, ~/.zshrc, etc.):
""")
    print('  export SLACK_BOT_TOKEN="xoxb-your-token-here"')
    print('  export SLACK_PROGRESS_CHANNEL="C07XXXXXXXX"')
    print('  export SLACK_ALERTS_CHANNEL="C07XXXXXXXX"')
    print('  export SLACK_FEEDBACK_CHANNEL="C07XXXXXXXX"')
    print("""
Step 6: Test
  → Run: python3 slack.py test
  → Check #game-agent-progress for the test message
""")


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "init":
        cmd_init()
    elif cmd == "run":
        once = "--once" in sys.argv
        dry = "--dry-run" in sys.argv
        cmd_run(once=once, dry_run=dry)
    elif cmd == "status":
        cmd_status()
    elif cmd == "report":
        # Delegate to daily-report.py
        os.environ["GAME_AGENT_PROJECT_DIR"] = str(PROJECT_DIR)
        os.execvp("python3", ["python3", str(PROJECT_DIR / "daily-report.py")])
    elif cmd == "gate":
        phase = sys.argv[2] if len(sys.argv) > 2 else "1"
        cmd_gate(phase)
    elif cmd == "health":
        mode = sys.argv[2] if len(sys.argv) > 2 else "full"
        os.environ["GAME_AGENT_PROJECT_DIR"] = str(PROJECT_DIR)
        os.execvp("python3", ["python3", str(PROJECT_DIR / "healthcheck.py"), mode])
    elif cmd == "setup-slack":
        cmd_setup_slack()
    elif cmd == "test-slack":
        os.environ["GAME_AGENT_PROJECT_DIR"] = str(PROJECT_DIR)
        os.execvp("python3", ["python3", str(PROJECT_DIR / "slack.py"), "test"])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
