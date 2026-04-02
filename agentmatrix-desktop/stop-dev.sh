#!/bin/bash

# AgentMatrix Desktop Development Stop Script

echo "🛑 Stopping AgentMatrix Desktop Development Environment..."
echo ""

# Stop Tauri application (cargo run and the binary)
echo "Stopping Tauri application..."
pkill -9 -f "cargo run" 2>/dev/null && echo "   Stopped cargo run" || true
pkill -9 -f "target/debug/agentmatrix" 2>/dev/null && echo "   Stopped Tauri binary" || true
# Also kill by port 1420 (Tauri dev server)
lsof -ti:1420 2>/dev/null | xargs kill -9 2>/dev/null && echo "   Stopped process on port 1420" || true
echo "✅ Tauri app cleanup done"

# Stop Vite dev server (also kill by port 5173)
echo "Stopping Vite dev server..."
pkill -9 -f "vite" 2>/dev/null && echo "   Stopped vite processes" || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null && echo "   Stopped process on port 5173" || true
echo "✅ Vite server cleanup done"

# Stop Python backend
echo "Stopping Python backend..."
pkill -9 -f "python.*server.py" 2>/dev/null && echo "   Stopped python server" || true
# Also kill common Python backend ports (force kill)
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null && echo "   Stopped process on port 8000" || true
echo "✅ Python backend cleanup done"

echo ""
echo "✅ All services stopped"
echo ""
echo "💡 Tip: Start again with: ./start-dev.sh"
