#!/bin/bash

# AgentMatrix Desktop Development Stop Script

echo "🛑 Stopping AgentMatrix Desktop Development Environment..."
echo ""

# Stop Tauri application (cargo run and the binary)
echo "Stopping Tauri application..."
pkill -f "cargo run" 2>/dev/null && echo "   Stopped cargo run" || true
pkill -f "target/debug/agentmatrix" 2>/dev/null && echo "   Stopped Tauri binary" || true
# Also kill by port 1420 (Tauri dev server)
lsof -ti:1420 | xargs kill 2>/dev/null && echo "   Stopped process on port 1420" || true
echo "✅ Tauri app cleanup done"

# Stop Vite dev server (also kill by port 5173)
echo "Stopping Vite dev server..."
pkill -f "vite" 2>/dev/null && echo "   Stopped vite processes" || true
lsof -ti:5173 | xargs kill 2>/dev/null && echo "   Stopped process on port 5173" || true
echo "✅ Vite server cleanup done"

# Stop Python backend
echo "Stopping Python backend..."
pkill -f "python.*server.py" 2>/dev/null && echo "   Stopped python server" || true
# Also kill common Python backend ports
lsof -ti:8000 2>/dev/null | xargs kill 2>/dev/null && echo "   Stopped process on port 8000" || true
lsof -ti:8080 2>/dev/null | xargs kill 2>/dev/null && echo "   Stopped process on port 8080" || true
echo "✅ Python backend cleanup done"

echo ""
echo "✅ All services stopped"
echo ""
echo "💡 Tip: Start again with: ./start-dev.sh"
