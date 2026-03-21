#!/bin/bash

# AgentMatrix Desktop Development Startup Script
# Usage:
#   ./start-dev.sh                # Normal startup
#   ./start-dev.sh --force-wizard # Force cold start wizard every time

set -e

PROJECT_DIR="/Users/dkt/myprojects/agentmatrix"
cd "$PROJECT_DIR/agentmatrix-desktop"

echo "🚀 Starting AgentMatrix Desktop Development Environment..."

# Parse arguments
FORCE_WIZARD=false
for arg in "$@"; do
    case $arg in
        --force-wizard)
            FORCE_WIZARD=true
            export AGENTMATRIX_FORCE_WIZARD=1
            echo "🧪 Force wizard mode enabled (AGENTMATRIX_FORCE_WIZARD=1)"
            ;;
    esac
done

echo ""

# 设置 PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
echo "🐍 PYTHONPATH set to: $PROJECT_DIR/src"

# Check if processes are already running
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Vite dev server already running on port 5173"
else
    echo "📱 Starting Vite dev server..."
    npm run dev > /tmp/vite-dev.log 2>&1 &
    VITE_PID=$!
    echo "   Vite server PID: $VITE_PID"
    echo "   Waiting for Vite to start..."
    sleep 3
    if curl -s http://localhost:5173 > /dev/null; then
        echo "   ✅ Vite server ready at http://localhost:5173"
    else
        echo "   ❌ Vite server failed to start"
        echo "   Check logs: tail -f /tmp/vite-dev.log"
        exit 1
    fi
fi

echo ""
echo "🪟 Starting Tauri desktop application..."
echo "   (This will automatically start the Python backend)"
if [ "$FORCE_WIZARD" = true ]; then
    echo "   🧪 Wizard will show every time (force mode)"
fi
echo ""

cd src-tauri
source /Users/dkt/.cargo/env
cargo run
