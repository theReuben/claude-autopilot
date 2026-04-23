# Claude Autopilot

Hands-free automation for Claude Code projects. Define your project in YAML, run `autopilot`, and let Claude build it autonomously — with progress tracking, Slack updates, quality gates, and adaptive ETAs.

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

## Install

```bash
git clone https://github.com/your-org/claude-autopilot.git
pip install -e ./claude-autopilot
```

This installs the `autopilot` command globally. The tool lives in its own directory — no files are copied into your projects.

## Quick Start

```bash
# 1. Create autopilot.yaml in your project repo
cd my-project
cp /path/to/claude-autopilot/autopilot.example.yaml autopilot.yaml
# Edit autopilot.yaml — define your phases, steps, and substeps

# 2. Scaffold the project
autopilot init

# 3. Create skeleton knowledge-base files (API references, templates)
autopilot docs

# 4. Fill in the generated files
#    - MASTER_PLAN.md: add detailed instructions for each step
#    - CLAUDE.md: add your project-specific conventions
#    - docs/api-reference/*.md: paste in the API docs Claude will need
#    - docs/patterns/*: fill in the code templates

# 5. Set up Slack (optional but recommended)
autopilot setup-slack

# 6. Run
autopilot run
```

## Design

Autopilot is installed once as a tool and used across many projects. All configuration for the work lives in the project repo — autopilot brings none of its own opinions about what you're building.

```
~/.local/                          your-project/
  claude-autopilot/       ──────►  autopilot.yaml     ← define the work here
    autopilot.py   (tool)          PROGRESS.md        ← generated, updated by Claude
    slack.py                       CLAUDE.md          ← generated, edit conventions
    healthcheck.py                 MASTER_PLAN.md     ← generated, add instructions
    ...                            FEEDBACK.md        ← generated, human ↔ Claude
                                   docs/              ← your API refs and templates
```

## Configuration

Everything is defined in `autopilot.yaml` in your project root:

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

knowledge:
  references:
    - path: "docs/api-reference/my-framework.md"
      description: "Framework API reference"
      relevant_steps: ["1.1", "1.2"]
  templates:
    - path: "docs/patterns/route-template.ts"
      description: "Template for new route handlers"
```

See `autopilot.example.yaml` for all options.

## Commands

| Command | What it does |
|---|---|
| `autopilot init` | Scaffold project from autopilot.yaml (PROGRESS.md, CLAUDE.md, etc.) |
| `autopilot docs` | Create skeleton files for knowledge.references and knowledge.templates |
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
0 0,6,11,17 * * * cd /path/to/project && autopilot run >> .automation/logs/cron.log 2>&1
```

**Windows (Task Scheduler):**
```powershell
$Action = New-ScheduledTaskAction -Execute "autopilot" -Argument "run"
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 5 -Minutes 30)
Register-ScheduledTask -TaskName "Autopilot" -Action $Action -Trigger $Trigger
```

**Daily report:**
```bash
0 8 * * * cd /path/to/project && autopilot report >> .automation/logs/report.log 2>&1
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
├── autopilot.yaml           # Your project config (the only autopilot file you own)
├── CLAUDE.md                # Generated — project conventions for Claude
├── MASTER_PLAN.md           # Generated — step-by-step instructions
├── PROGRESS.md              # Generated — progress tracker (updated by Claude)
├── FEEDBACK.md              # Generated — human feedback (synced from Slack)
├── .claudeignore            # Generated — keeps noise out of context
├── docs/
│   ├── cookbook.md          # Grows during project — bug fixes & workarounds
│   ├── decisions.md         # Architecture Decision Records
│   ├── api-reference/       # Skeleton created by `autopilot docs`, fill in content
│   └── patterns/            # Skeleton created by `autopilot docs`, fill in templates
└── .automation/
    ├── logs/                # Session logs
    ├── backups/             # Critical file backups
    └── run-session.sh       # Generated — do not edit
```

## Examples

See `examples/` for complete project configs:
- `examples/game-agent/` — Blender/Unity MCP server system

## Requirements

- Python 3.9+
- Claude Code (`npm install -g @anthropic-ai/claude-code`)
- Git
- Authenticated Claude Code (Pro, Max, or API key)
