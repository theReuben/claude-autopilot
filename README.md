# Claude Autopilot

Hands-free automation for Claude Code projects. Define your project in YAML, schedule it, and let Claude build it autonomously — with progress tracking, Slack updates, quality gates, and adaptive ETAs.

## What It Does

```
You define a plan          Autopilot runs Claude Code     You get updates
┌──────────────┐          ┌────────────────────────┐     ┌──────────────┐
│autopilot.yaml│ ───────► │ Sessions drain the 5h  │ ──► │ #progress    │
│              │          │ window automatically.  │     │ #alerts      │
│ Phases       │          │ PROGRESS.md tracks     │     │ #feedback    │
│ Steps        │          │ state across sessions. │     │ Daily ETAs   │
│ Gates        │          │ Phase gates validate.  │     │ Velocity 📈  │
└──────────────┘          └────────────────────────┘     └──────────────┘
```

- **Drains your token window** — runs sessions back-to-back until rate limited
- **Picks the right model** — Opus for architecture, Sonnet for implementation (configurable per step)
- **Tracks progress** — PROGRESS.md with substep checkboxes, persists across sessions
- **Phase gates** — validates required files and commands before advancing
- **Slack integration** — real-time session updates, alerts, and bi-directional feedback
- **Daily reports** — velocity tracking, per-phase ETAs, blocker detection
- **Healthchecks** — pre/post flight validation with auto-fix
- **Rollback** — git tags at every step advance and phase completion
- **Code review notice** — tells Claude its work will be audited (improves output quality)
- **Feedback loop** — post in Slack, Claude reads it before the next session

## Quick Start

```bash
# 1. Install
pip install pyyaml
git clone https://github.com/your-org/claude-autopilot.git
cd claude-autopilot

# 2. Create your project
mkdir my-project && cd my-project
cp ../claude-autopilot/autopilot.example.yaml autopilot.yaml
# Edit autopilot.yaml with your phases, steps, and substeps

# 3. Scaffold
python3 ../claude-autopilot/autopilot.py init

# 4. Edit the generated files
#    - CLAUDE.md: add your project conventions
#    - MASTER_PLAN.md: add detailed step instructions
#    - docs/api-reference/: add API docs Claude should reference

# 5. Set up Slack (optional but recommended)
python3 ../claude-autopilot/autopilot.py setup-slack

# 6. Run
python3 ../claude-autopilot/autopilot.py run
```

## Configuration

Everything is defined in `autopilot.yaml`:

```yaml
project:
  name: "My API Server"

phases:
  - name: "Foundation"
    steps:
      - id: "1.1"
        name: "Database schema"
        model: opus          # Use Opus for this step
        substeps:
          - "Design schema"
          - "Write migrations"
          - "Add seed data"
      - id: "1.2"
        name: "REST endpoints"
        model: sonnet        # Use Sonnet (cheaper, faster)
        substeps:
          - "GET /users"
          - "POST /users"
          - "Error handling"
    gate:
      required_files:
        - "src/db/schema.sql"
        - "src/routes/users.ts"
      checks:
        - "npm run build"
        - "npm test"

session:
  max_turns: 75              # Turns per session
  permission_mode: "auto"    # auto-approve safe actions

review:
  enabled: true
  reviewer: "Codex"          # Tell Claude who reviews its work

slack:
  enabled: true
```

See `autopilot.example.yaml` for all options.

## Commands

| Command | What it does |
|---|---|
| `autopilot init` | Scaffold project from autopilot.yaml (PROGRESS.md, CLAUDE.md, etc.) |
| `autopilot run` | Drain the token window — sessions until rate limited |
| `autopilot run --once` | Run a single session |
| `autopilot run --dry-run` | Preview the prompt without running |
| `autopilot status` | Show progress bar and current step |
| `autopilot report` | Send daily report (Slack + email) |
| `autopilot gate <N>` | Run phase N gate validation |
| `autopilot health` | Run full diagnostic |
| `autopilot health fix` | Auto-fix common issues |
| `autopilot setup-slack` | Interactive Slack setup guide |
| `autopilot test-slack` | Send test message to Slack |

## Scheduling

Schedule `autopilot run` every 5.5 hours to maximize output:

**Linux/Mac (cron):**
```bash
crontab -e
0 0,6,11,17 * * * cd /path/to/project && python3 /path/to/autopilot.py run >> .automation/logs/cron.log 2>&1
```

**Windows (Task Scheduler):**
```powershell
$Action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\autopilot.py run"
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 5 -Minutes 30)
Register-ScheduledTask -TaskName "Autopilot" -Action $Action -Trigger $Trigger
```

**Daily report:**
```bash
0 8 * * * cd /path/to/project && python3 /path/to/autopilot.py report >> .automation/logs/report.log 2>&1
```

## Slack Channels

| Channel | Purpose | Who posts |
|---|---|---|
| `#progress` | Session updates, window summaries, daily reports with ETAs | Bot |
| `#alerts` | Phase completions, stalls, errors, gate results | Bot |
| `#feedback` | Instructions and corrections | **You** |

Post anything in `#feedback` and the bot picks it up before the next session:
- *"Skip Step 2.7, not needed yet"*
- *"The export crashes — check context override"*
- *"STOP — do not advance past Step 2.6"*

## How It Works

Each scheduled run:
1. **Syncs feedback** from Slack → FEEDBACK.md
2. **Pre-flight healthcheck** — verifies project state, auto-fixes if needed
3. **Backs up** critical files (PROGRESS.md, CLAUDE.md, cookbook)
4. **Builds a prompt** with current step, remaining window time, and all instructions
5. **Runs `claude -p`** with the right model, max turns, and auto permissions
6. **Post-flight healthcheck** — verifies output, commits to git
7. **Tags rollback point** in git if step advanced
8. **Runs phase gate** if a phase's last step completed
9. **Loops** — repeats until rate limited or window expires
10. **Posts summary** to Slack

## File Structure After Init

```
your-project/
├── autopilot.yaml          # Your project config
├── CLAUDE.md               # Generated — project conventions for Claude
├── MASTER_PLAN.md          # Generated — step-by-step instructions
├── PROGRESS.md             # Generated — progress tracker (updated by Claude)
├── FEEDBACK.md             # Generated — human feedback (synced from Slack)
├── .claudeignore            # Generated — keeps noise out of context
├── docs/
│   ├── cookbook.md          # Grows during project — bug fixes & workarounds
│   ├── decisions.md        # Architecture Decision Records
│   └── api-reference/      # Your API docs (Claude reads these)
└── .automation/
    ├── logs/               # Session logs
    ├── backups/            # Critical file backups
    └── velocity.json       # ETA tracking data
```

## Examples

See `examples/` for complete project configs:
- `examples/game-agent/` — Blender/Unity MCP server system (the project this tool was extracted from)

## Requirements

- Python 3.9+
- PyYAML (`pip install pyyaml`)
- Claude Code (`npm install -g @anthropic-ai/claude-code`)
- Git
- Authenticated Claude Code (Pro, Max, or API key)
