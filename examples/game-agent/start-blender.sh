#!/bin/bash
# ============================================================================
# Blender Auto-Launcher
# ============================================================================
# Ensures Blender is running with the MCP addon before a Claude Code session.
# Called by run-session.sh automatically.
#
# Set BLENDER_PATH to your Blender executable if it's not on PATH.
# ============================================================================

BLENDER_PATH="${BLENDER_PATH:-blender}"
ADDON_PATH="$(cd "$(dirname "$0")" && pwd)/mcp-servers/blender-mcp/blender_addon.py"
BLENDER_PORT=9876
STARTUP_WAIT=15

# Check if Blender addon is already responding
check_blender() {
    nc -z localhost "$BLENDER_PORT" 2>/dev/null
    return $?
}

if check_blender; then
    echo "[Blender] Already running on port $BLENDER_PORT"
    exit 0
fi

echo "[Blender] Not detected on port $BLENDER_PORT. Starting..."

if ! command -v "$BLENDER_PATH" &>/dev/null; then
    echo "[Blender] ERROR: '$BLENDER_PATH' not found."
    echo "  Set BLENDER_PATH environment variable to your Blender executable."
    echo "  Example: export BLENDER_PATH=\"/Applications/Blender.app/Contents/MacOS/Blender\""
    echo "  Example: export BLENDER_PATH=\"C:/Program Files/Blender Foundation/Blender 4.2/blender.exe\""
    exit 1
fi

if [[ ! -f "$ADDON_PATH" ]]; then
    echo "[Blender] WARNING: Addon not found at $ADDON_PATH"
    echo "  Blender will start but the MCP bridge won't be active."
    echo "  Build the addon first (Phase 1, Step 1.1)."
    exit 1
fi

# Launch Blender in background mode with the addon
# --background = headless (no GUI). Remove this flag if you want the GUI.
nohup "$BLENDER_PATH" --background --python "$ADDON_PATH" \
    > "$(dirname "$0")/.automation/logs/blender.log" 2>&1 &

BLENDER_PID=$!
echo "[Blender] Started with PID $BLENDER_PID. Waiting ${STARTUP_WAIT}s for startup..."
sleep "$STARTUP_WAIT"

if check_blender; then
    echo "[Blender] Ready on port $BLENDER_PORT"
else
    echo "[Blender] WARNING: Started but not responding on port $BLENDER_PORT yet."
    echo "  The addon may not be loaded. Check .automation/logs/blender.log"
fi
