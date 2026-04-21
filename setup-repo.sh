#!/bin/bash
# ============================================================================
# Push Claude Autopilot to GitHub
# ============================================================================
# Run this from the directory where you unzipped claude-autopilot.zip
#
# Usage:
#   chmod +x setup-repo.sh
#   ./setup-repo.sh
# ============================================================================

set -euo pipefail

REPO_NAME="claude-autopilot"
GITHUB_USER=""  # Will be detected or prompted

echo "╔══════════════════════════════════════════════════╗"
echo "║     Claude Autopilot — GitHub Repository Setup   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── Step 1: Check prerequisites ───────────────────────────────────────────

echo "[1/6] Checking prerequisites..."

if ! command -v git &>/dev/null; then
    echo "  ❌ git not found. Install: https://git-scm.com"
    exit 1
fi
echo "  ✅ git"

if ! command -v gh &>/dev/null; then
    echo "  ⚠ GitHub CLI (gh) not found — you'll need to create the repo manually"
    echo "    Install: https://cli.github.com"
    HAS_GH=false
else
    echo "  ✅ gh (GitHub CLI)"
    HAS_GH=true
fi

# ─── Step 2: Detect GitHub user ────────────────────────────────────────────

echo ""
echo "[2/6] Detecting GitHub user..."

if [[ "$HAS_GH" == true ]]; then
    GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null || echo "")
fi

if [[ -z "$GITHUB_USER" ]]; then
    GITHUB_USER=$(git config --global user.name 2>/dev/null || echo "")
fi

if [[ -z "$GITHUB_USER" ]]; then
    read -p "  GitHub username: " GITHUB_USER
fi

echo "  User: $GITHUB_USER"

# ─── Step 3: Initialize git ────────────────────────────────────────────────

echo ""
echo "[3/6] Initializing git repository..."

if [[ -d .git ]]; then
    echo "  Already a git repo — skipping init"
else
    git init
    echo "  ✅ git init"
fi

# Create .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
.env
.automation/
*.egg-info/
dist/
build/
EOF
echo "  ✅ .gitignore"

# ─── Step 4: Stage and commit ──────────────────────────────────────────────

echo ""
echo "[4/6] Staging files..."

git add -A
git commit -m "Initial commit: Claude Autopilot v1.0

Hands-free automation for Claude Code projects.
- YAML-based project configuration
- Automatic session management (drains 5h token windows)
- Slack integration (progress, alerts, feedback)
- Phase gates with validation
- Health checks with auto-fix
- Velocity tracking and ETA reports
- Opus/Sonnet model selection per step
- Git rollback tags at every checkpoint" 2>/dev/null || echo "  (already committed)"

echo "  ✅ Committed"

# ─── Step 5: Create GitHub repo ────────────────────────────────────────────

echo ""
echo "[5/6] Creating GitHub repository..."

if [[ "$HAS_GH" == true ]]; then
    # Check if repo already exists
    if gh repo view "$GITHUB_USER/$REPO_NAME" &>/dev/null 2>&1; then
        echo "  Repo $GITHUB_USER/$REPO_NAME already exists"
    else
        read -p "  Create public repo $GITHUB_USER/$REPO_NAME? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            gh repo create "$REPO_NAME" \
                --public \
                --description "Hands-free automation for Claude Code projects. Define phases in YAML, schedule it, get Slack updates." \
                --source . \
                --remote origin
            echo "  ✅ Repo created"
        else
            echo "  Skipped — create manually at https://github.com/new"
        fi
    fi
else
    echo "  ⚠ GitHub CLI not available. Create the repo manually:"
    echo ""
    echo "    1. Go to https://github.com/new"
    echo "    2. Name: $REPO_NAME"
    echo "    3. Description: Hands-free automation for Claude Code projects"
    echo "    4. Public"
    echo "    5. Do NOT initialize with README (we already have one)"
    echo "    6. Click Create"
    echo "    7. Then run:"
    echo "       git remote add origin https://github.com/$GITHUB_USER/$REPO_NAME.git"
    echo ""
    read -p "  Press Enter when you've created the repo..." -r
fi

# ─── Step 6: Push ──────────────────────────────────────────────────────────

echo ""
echo "[6/6] Pushing to GitHub..."

# Ensure we have a remote
if git remote get-url origin &>/dev/null 2>&1; then
    git branch -M main
    git push -u origin main
    echo "  ✅ Pushed to https://github.com/$GITHUB_USER/$REPO_NAME"
else
    echo "  ⚠ No remote 'origin' configured. Add it and push:"
    echo "     git remote add origin https://github.com/$GITHUB_USER/$REPO_NAME.git"
    echo "     git branch -M main"
    echo "     git push -u origin main"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Done! Your repo is ready.                       ║"
echo "║                                                  ║"
echo "║  https://github.com/$GITHUB_USER/$REPO_NAME"
echo "║                                                  ║"
echo "║  Next steps:                                     ║"
echo "║  • Add topics: claude, automation, ai, claude-code║"
echo "║  • Star your own repo (visibility boost)         ║"
echo "║  • Share it!                                     ║"
echo "╚══════════════════════════════════════════════════╝"
