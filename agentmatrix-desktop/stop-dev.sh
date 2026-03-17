#!/bin/bash

# AgentMatrix Desktop Development Stop Script

echo "🛑 Stopping AgentMatrix Desktop Development Environment..."
echo ""

# Stop Tauri application
echo "Stopping Tauri application..."
pkill -f "target/debug/agentmatrix" && echo "✅ Tauri app stopped" || echo "⚠️  Tauri app not running"

# Stop Vite dev server  
echo "Stopping Vite dev server..."
pkill -f "vite" && echo "✅ Vite server stopped" || echo "⚠️  Vite server not running"

# Stop Python backend
echo "Stopping Python backend..."
pkill -f "python.*server.py" && echo "✅ Python backend stopped" || echo "⚠️  Python backend not running"

echo ""
echo "✅ All services stopped"
echo ""
echo "💡 Tip: Start again with: ./start-dev.sh"
