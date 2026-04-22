#!/bin/bash

# AgentMatrix Desktop Development Startup Script
# Usage:
#   ./start-dev.sh                # Normal startup
#   ./start-dev.sh --force-wizard # Force cold start wizard every time

set -e

# Auto-detect project root from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT_DIR="$(dirname "$PROJECT_DIR")"  # 指向 agentmatrix 根目录
cd "$SCRIPT_DIR"

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
echo "📁 PROJECT_DIR: $PROJECT_DIR"

# Copy matrix-template to configured locations
MATRIX_TEMPLATE_SRC="$PROJECT_DIR/matrix-template"
SETTINGS_FILE="$HOME/.agentmatrix/settings.json"

if [ -d "$MATRIX_TEMPLATE_SRC" ]; then
    echo ""
    echo "📋 Syncing matrix-template..."

    # Copy to Tauri resources directory (for packaging) - complete copy
    # NOTE: This is for packaging, don't delete existing files that may be in git
    TEMPLATE_RESOURCES_DST="$SCRIPT_DIR/src-tauri/resources/matrix-template"
    echo "   → Copying to Tauri resources: $TEMPLATE_RESOURCES_DST"
    mkdir -p "$TEMPLATE_RESOURCES_DST"
    # Use rsync WITHOUT --delete to avoid removing files that are in git
    rsync -a "$MATRIX_TEMPLATE_SRC/" "$TEMPLATE_RESOURCES_DST/" 2>/dev/null || \
        cp -rf "$MATRIX_TEMPLATE_SRC"/. "$TEMPLATE_RESOURCES_DST"/
    echo "   ✅ Synced to $TEMPLATE_RESOURCES_DST"

    echo ""
else
    echo "   ⚠️  matrix-template source not found: $MATRIX_TEMPLATE_SRC"
    echo ""
fi

# Ensure resource directories exist (CI downloads installers, dev mode needs placeholders)
mkdir -p "$SCRIPT_DIR/src-tauri/resources/podman"
touch "$SCRIPT_DIR/src-tauri/resources/podman/.gitkeep" 2>/dev/null || true

# python_dist is only needed for production builds (PyInstaller output)
# Dev mode uses 'python server.py' directly, but tauri.conf.json glob requires the dir to exist
mkdir -p "$SCRIPT_DIR/src-tauri/resources/python_dist"
touch "$SCRIPT_DIR/src-tauri/resources/python_dist/.gitkeep" 2>/dev/null || true

# Copy template to where Tauri expects it in dev mode
TEMPLATE_SRC="$SCRIPT_DIR/src-tauri/resources/matrix-template"
TEMPLATE_DST="$SCRIPT_DIR/src-tauri/target/debug/matrix-template"
if [ -d "$TEMPLATE_SRC" ]; then
    rm -rf "$TEMPLATE_DST"
    mkdir -p "$(dirname "$TEMPLATE_DST")"
    cp -r "$TEMPLATE_SRC" "$TEMPLATE_DST"
    echo "📦 Synced matrix-template to target/debug/"
fi

# Check if processes are already running
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    # Verify it's actually a Vite/Node process, not a stale listener
    VITE_PID=$(lsof -Pi :5173 -sTCP:LISTEN -t 2>/dev/null | head -1)
    if ps -p "$VITE_PID" -o comm= 2>/dev/null | grep -qiE "node|vite"; then
        echo "⚠️  Vite dev server already running on port 5173 (PID: $VITE_PID)"
    else
        echo "⚠️  Port 5173 occupied by non-Vite process (PID: $VITE_PID), killing it..."
        kill "$VITE_PID" 2>/dev/null || true
        sleep 1
        # Fall through to start Vite
        VITE_PID=""
    fi
fi

# Start Vite if not already running
if [ -z "${VITE_PID:-}" ] || ! lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "📱 Starting Vite dev server..."
    npm run dev > /tmp/vite-dev.log 2>&1 &
    VITE_PID=$!
    echo "   Vite server PID: $VITE_PID"
    echo "   Waiting for Vite to start..."

    # Retry loop - wait up to 15 seconds for server to be ready
    READY=false
    for i in $(seq 1 15); do
        sleep 1
        # Use 127.0.0.1 to avoid IPv6 issues, follow redirects
        if curl -s -f -o /dev/null --max-time 2 http://127.0.0.1:5173/ 2>/dev/null; then
            READY=true
            break
        fi
    done

    if [ "$READY" = true ]; then
        echo "   ✅ Vite server ready at http://localhost:5173"
    else
        echo "   ⚠️  Vite health check inconclusive, checking if process is running..."
        if kill -0 $VITE_PID 2>/dev/null; then
            echo "   ✅ Vite server process (PID: $VITE_PID) is running"
            echo "   💡 You can access it at http://localhost:5173"
        else
            echo "   ❌ Vite server failed to start"
            echo "   Check logs: tail -f /tmp/vite-dev.log"
            exit 1
        fi
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

# Create placeholder sidecar binary for local development
# This is needed because Tauri's externalBin requires the binary to exist during compilation
# The Rust code will detect this is a placeholder and fall back to using 'python server.py'
TAURI_TARGET="${TAURI_TARGET:-$(rustc -vV | grep ^host: | cut -d' ' -f2)}"
BINARY_DIR="binaries"
SIDECAR_BINARY="$BINARY_DIR/server-$TAURI_TARGET"

if [ ! -f "$SIDECAR_BINARY" ]; then
    echo "📦 Creating placeholder sidecar for local development..."
    mkdir -p "$BINARY_DIR"
    cat > "$SIDECAR_BINARY" << 'EOF'
#!/bin/bash
# Placeholder for Tauri sidecar binary (local development only)
# CI/CD will replace this with the real PyInstaller-built binary
# The Rust code detects this and falls back to 'python server.py'
echo "Placeholder: using python server.py instead"
EOF
    chmod +x "$SIDECAR_BINARY"
    echo "   ✅ Created placeholder: $SIDECAR_BINARY"
fi

source /Users/dkt/.cargo/env
cargo run
