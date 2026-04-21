#!/usr/bin/env python3
"""
============================================================================
Game Agent System — Health Checks & Validation
============================================================================
Run before and after each automated session to catch problems early.
Called by run-session.sh automatically.

Usage:
  python3 healthcheck.py pre          # Before a session
  python3 healthcheck.py post         # After a session
  python3 healthcheck.py full         # Full diagnostic
  python3 healthcheck.py fix          # Auto-fix common issues

Exit codes:
  0 = all clear
  1 = warnings (proceed with caution)
  2 = blockers (do not run session)
============================================================================
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_DIR = os.environ.get("GAME_AGENT_PROJECT_DIR", os.path.dirname(os.path.abspath(__file__)))
PROGRESS_FILE = os.path.join(PROJECT_DIR, "PROGRESS.md")
MAX_WARNINGS = 0
issues = []
warnings = []


def check(name, condition, fix_hint=None, is_warning=False):
    """Register a check result."""
    if not condition:
        msg = f"{'⚠' if is_warning else '❌'} {name}"
        if fix_hint:
            msg += f"\n   Fix: {fix_hint}"
        if is_warning:
            warnings.append(msg)
        else:
            issues.append(msg)
    else:
        print(f"  ✅ {name}")


# ─── Pre-Flight Checks (run before each session) ───────────────────────────

def preflight():
    """Verify the project is in a runnable state before starting a session."""
    print("═══ PRE-FLIGHT CHECKS ═══\n")

    # 1. Critical files exist
    print("[Files]")
    check("CLAUDE.md exists", os.path.exists(os.path.join(PROJECT_DIR, "CLAUDE.md")),
          "Restore from git or re-download phase0 package")
    check("PROGRESS.md exists", os.path.exists(PROGRESS_FILE),
          "Restore from git or re-download phase0 package")
    check("MASTER_PLAN.md exists", os.path.exists(os.path.join(PROJECT_DIR, "MASTER_PLAN.md")),
          "Restore from git or re-download phase0 package")
    check(".claudeignore exists", os.path.exists(os.path.join(PROJECT_DIR, ".claudeignore")),
          "Restore from git — without this, Claude will scan Library/ and waste tokens")

    # 2. PROGRESS.md is parseable
    print("\n[Progress File Integrity]")
    if os.path.exists(PROGRESS_FILE):
        content = Path(PROGRESS_FILE).read_text(encoding="utf-8")
        check("Active Phase is parseable",
              bool(re.search(r'\*\*Active Phase:\*\*\s*\d+', content)),
              "PROGRESS.md may be corrupted — check the header section")
        check("Active Step is parseable",
              bool(re.search(r'\*\*Active Step:\*\*\s*[\d.]+', content)),
              "PROGRESS.md may be corrupted — check the header section")
        check("Next Action is parseable",
              bool(re.search(r'\*\*Next Action:\*\*\s*.+', content)),
              "PROGRESS.md may be corrupted — check the header section")
        check("Session Log table exists",
              "Session #" in content or "| 1 |" in content or "Session Log" in content,
              "Session Log table may have been deleted", is_warning=True)
        check("No merge conflict markers",
              "<<<<<<" not in content and ">>>>>>>" not in content,
              "PROGRESS.md has merge conflicts — resolve manually")
        # Check for reasonable substep counts
        done = len(re.findall(r'\[x\]', content, re.IGNORECASE))
        total = len(re.findall(r'\[[ x]\]', content, re.IGNORECASE))
        check(f"Substep counts reasonable ({done}/{total})",
              total > 50 and done <= total,
              "Substep count looks wrong — PROGRESS.md may be corrupted")

    # 3. Git is clean
    print("\n[Git State]")
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_DIR,
                                capture_output=True, text=True, timeout=10)
        check("Git working tree is clean",
              result.stdout.strip() == "",
              "Uncommitted changes exist. Run: git add -A && git commit -m 'manual cleanup'",
              is_warning=True)

        # Check for merge conflicts
        result = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=PROJECT_DIR,
                                capture_output=True, text=True, timeout=10)
        check("No merge conflicts",
              result.stdout.strip() == "",
              "Resolve merge conflicts before running: git mergetool")

        # Check branch
        result = subprocess.run(["git", "branch", "--show-current"], cwd=PROJECT_DIR,
                                capture_output=True, text=True, timeout=10)
        branch = result.stdout.strip()
        check(f"On expected branch ('{branch}')",
              branch in ("main", "master", "dev", "development"),
              f"Currently on branch '{branch}' — is this intentional?", is_warning=True)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        issues.append("❌ Git not available or timed out")

    # 4. Disk space
    print("\n[System]")
    try:
        import shutil
        total, used, free = shutil.disk_usage(PROJECT_DIR)
        free_gb = free / (1024**3)
        check(f"Disk space OK ({free_gb:.1f} GB free)",
              free_gb > 2.0,
              f"Only {free_gb:.1f} GB free — Unity projects need space")
    except Exception:
        warnings.append("⚠ Could not check disk space")

    # 5. Dependencies accessible
    print("\n[Dependencies]")
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
        check("Claude Code installed", result.returncode == 0,
              "Install: npm install -g @anthropic-ai/claude-code")
    except FileNotFoundError:
        issues.append("❌ Claude Code not found on PATH")

    # Check if Node.js is available (for Unity MCP server)
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        check("Node.js installed", result.returncode == 0,
              "Install Node.js: https://nodejs.org")
    except FileNotFoundError:
        warnings.append("⚠ Node.js not found (needed for Unity MCP server)")

    # Check if Python packages are available
    try:
        import fastmcp
        check("FastMCP installed", True)
    except ImportError:
        warnings.append("⚠ FastMCP not installed (needed for Blender MCP server: pip install fastmcp)")


# ─── Post-Flight Checks (run after each session) ───────────────────────────

def postflight():
    """Verify the session left the project in a good state."""
    print("═══ POST-FLIGHT CHECKS ═══\n")

    # 1. PROGRESS.md was updated
    print("[Progress Update]")
    if os.path.exists(PROGRESS_FILE):
        content = Path(PROGRESS_FILE).read_text(encoding="utf-8")

        # Check that the session log has a recent entry
        log_dates = re.findall(r'\|\s*\d+\s*\|\s*([\d-]+)', content)
        today = datetime.now().strftime("%Y-%m-%d")
        check("Session log updated today",
              any(today in d for d in log_dates) if log_dates else False,
              "Claude may not have updated PROGRESS.md before the session ended",
              is_warning=True)

        # Check no malformed markdown
        check("No broken markdown tables",
              content.count("| Session #") <= 1,
              "Session Log table may be duplicated")

    # 2. Compilation checks (if applicable files exist)
    print("\n[Code Quality]")

    # Check Python files parse correctly
    py_files = list(Path(PROJECT_DIR).rglob("mcp-servers/**/*.py"))
    for pf in py_files[:20]:  # Cap at 20
        try:
            compile(pf.read_text(encoding="utf-8"), str(pf), "exec")
            check(f"Python syntax OK: {pf.name}", True)
        except SyntaxError as e:
            issues.append(f"❌ Syntax error in {pf.name}: {e.msg} (line {e.lineno})")

    # Check TypeScript files exist if expected
    ts_dir = os.path.join(PROJECT_DIR, "mcp-servers", "unity-mcp", "src")
    if os.path.exists(ts_dir):
        ts_files = list(Path(ts_dir).rglob("*.ts"))
        check(f"TypeScript files present ({len(ts_files)} files)",
              len(ts_files) > 0, is_warning=True)

    # Check C# files for obvious issues
    cs_files = list(Path(PROJECT_DIR).rglob("unity-project/**/*.cs"))
    for cf in cs_files[:20]:
        content = cf.read_text(encoding="utf-8", errors="replace")
        check(f"C# file not empty: {cf.name}", len(content.strip()) > 10,
              f"{cf.name} appears empty or nearly empty")
        check(f"C# file has namespace: {cf.name}",
              "namespace " in content or "using " in content,
              f"{cf.name} may be incomplete", is_warning=True)

    # 3. Git state
    print("\n[Git State]")
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_DIR,
                                capture_output=True, text=True, timeout=10)
        check("All changes committed",
              result.stdout.strip() == "",
              "Session ended with uncommitted changes — committing now...",
              is_warning=True)
        if result.stdout.strip():
            # Auto-commit leftovers
            subprocess.run(["git", "add", "-A"], cwd=PROJECT_DIR, timeout=10)
            subprocess.run(["git", "commit", "-m", "Auto: post-flight commit of uncommitted changes"],
                           cwd=PROJECT_DIR, timeout=10)
    except Exception:
        pass

    # 4. Check CLAUDE.md hasn't been mangled
    print("\n[Config Integrity]")
    claude_md = os.path.join(PROJECT_DIR, "CLAUDE.md")
    if os.path.exists(claude_md):
        content = Path(claude_md).read_text(encoding="utf-8")
        check("CLAUDE.md has architecture section", "Architecture" in content,
              "CLAUDE.md may have been overwritten — restore from git")
        check("CLAUDE.md has file locations", "File Locations" in content,
              "CLAUDE.md may have been overwritten — restore from git")
        check("CLAUDE.md has gotchas", "Known Gotchas" in content,
              "CLAUDE.md gotchas section missing — restore from git")


# ─── Full Diagnostic ───────────────────────────────────────────────────────

def full_diagnostic():
    """Run all checks."""
    preflight()
    print()
    postflight()

    # Additional deep checks
    print("\n═══ DEEP CHECKS ═══\n")

    # Check for stale API references
    print("[API Reference Freshness]")
    api_dir = os.path.join(PROJECT_DIR, "docs", "api-reference")
    if os.path.exists(api_dir):
        for ref_file in Path(api_dir).glob("*.md"):
            mtime = datetime.fromtimestamp(ref_file.stat().st_mtime)
            age_days = (datetime.now() - mtime).days
            check(f"{ref_file.name} updated ({age_days}d ago)",
                  age_days < 30,
                  "API references may be stale — consider refreshing if hitting errors",
                  is_warning=True)

    # Check cookbook growth
    print("\n[Cookbook Health]")
    cookbook = os.path.join(PROJECT_DIR, "docs", "cookbook.md")
    if os.path.exists(cookbook):
        content = Path(cookbook).read_text(encoding="utf-8")
        entry_count = content.count("### ") + content.count("## Problem")
        check(f"Cookbook has entries ({entry_count})",
              entry_count >= 5,
              "Cookbook seems small — are discoveries being recorded?", is_warning=True)

    # Check velocity data
    print("\n[Velocity Data]")
    velocity_file = os.path.join(PROJECT_DIR, ".automation", "velocity.json")
    if os.path.exists(velocity_file):
        data = json.loads(Path(velocity_file).read_text(encoding="utf-8"))
        snapshot_count = len(data.get("snapshots", []))
        check(f"Velocity history ({snapshot_count} snapshots)",
              snapshot_count >= 3,
              "Less than 3 days of data — ETAs will be unreliable", is_warning=True)
    else:
        warnings.append("⚠ No velocity data yet — run daily-report.py to start tracking")

    # Check log directory size
    print("\n[Storage]")
    log_dir = os.path.join(PROJECT_DIR, ".automation", "logs")
    if os.path.exists(log_dir):
        log_files = list(Path(log_dir).glob("*"))
        total_size = sum(f.stat().st_size for f in log_files if f.is_file())
        size_mb = total_size / (1024**2)
        check(f"Log directory size ({size_mb:.1f} MB, {len(log_files)} files)",
              size_mb < 500,
              "Logs are getting large — consider pruning old ones", is_warning=True)


# ─── Auto-Fix ──────────────────────────────────────────────────────────────

def auto_fix():
    """Attempt to fix common issues automatically."""
    print("═══ AUTO-FIX ═══\n")
    fixed = 0

    # 1. Commit uncommitted changes
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_DIR,
                                capture_output=True, text=True, timeout=10)
        if result.stdout.strip():
            print("Committing uncommitted changes...")
            subprocess.run(["git", "add", "-A"], cwd=PROJECT_DIR, timeout=10)
            subprocess.run(["git", "commit", "-m", "Auto-fix: commit uncommitted changes"],
                           cwd=PROJECT_DIR, timeout=10)
            fixed += 1
    except Exception as e:
        print(f"  Could not fix git state: {e}")

    # 2. Restore missing .claudeignore
    claudeignore = os.path.join(PROJECT_DIR, ".claudeignore")
    if not os.path.exists(claudeignore):
        print("Restoring .claudeignore...")
        try:
            subprocess.run(["git", "checkout", "HEAD", "--", ".claudeignore"],
                           cwd=PROJECT_DIR, timeout=10)
            fixed += 1
        except Exception:
            print("  Could not restore .claudeignore from git")

    # 3. Restore CLAUDE.md if mangled
    claude_md = os.path.join(PROJECT_DIR, "CLAUDE.md")
    if os.path.exists(claude_md):
        content = Path(claude_md).read_text(encoding="utf-8")
        if "Architecture" not in content or "File Locations" not in content:
            print("CLAUDE.md appears corrupted — restoring from git...")
            try:
                subprocess.run(["git", "checkout", "HEAD", "--", "CLAUDE.md"],
                               cwd=PROJECT_DIR, timeout=10)
                fixed += 1
            except Exception:
                print("  Could not restore CLAUDE.md from git")

    # 4. Prune old logs (keep last 30 days)
    log_dir = os.path.join(PROJECT_DIR, ".automation", "logs")
    if os.path.exists(log_dir):
        cutoff = datetime.now().timestamp() - (30 * 86400)
        pruned = 0
        for f in Path(log_dir).glob("window_*.log"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                pruned += 1
        if pruned:
            print(f"Pruned {pruned} old log files")
            fixed += 1

    # 5. Fix PROGRESS.md merge conflicts
    if os.path.exists(PROGRESS_FILE):
        content = Path(PROGRESS_FILE).read_text(encoding="utf-8")
        if "<<<<<<" in content:
            print("PROGRESS.md has merge conflicts — taking 'ours' version...")
            try:
                subprocess.run(["git", "checkout", "--ours", "--", "PROGRESS.md"],
                               cwd=PROJECT_DIR, timeout=10)
                subprocess.run(["git", "add", "PROGRESS.md"], cwd=PROJECT_DIR, timeout=10)
                fixed += 1
            except Exception:
                print("  Could not auto-resolve merge conflict")

    print(f"\nFixed {fixed} issue(s).")


# ─── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"

    if mode == "pre":
        preflight()
    elif mode == "post":
        postflight()
    elif mode == "full":
        full_diagnostic()
    elif mode == "fix":
        auto_fix()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: healthcheck.py [pre|post|full|fix]")
        sys.exit(1)

    print()
    if issues:
        print(f"{'═'*50}")
        print(f"BLOCKERS ({len(issues)}):")
        for i in issues:
            print(f"  {i}")
        print(f"{'═'*50}")
        sys.exit(2)
    elif warnings:
        print(f"{'─'*50}")
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")
        print(f"{'─'*50}")
        sys.exit(1)
    else:
        print("All checks passed ✅")
        sys.exit(0)
