#!/bin/bash

# AgentMatrix Backend Startup Script
# This script starts the Python backend server

set -e

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting AgentMatrix Backend Server..."
echo "📁 Project directory: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR"

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.8+"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "🐍 Python version: $PYTHON_VERSION"

# Check if required packages are installed
echo "📦 Checking dependencies..."
if ! python -c "import fastapi" 2>/dev/null; then
    echo "⚠️  FastAPI not found. Installing dependencies..."
    pip install -e .
fi

# Set default parameters
MATRIX_WORLD="${MATRIX_WORLD:-./MatrixWorld}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "🌐 Starting server on http://$HOST:$PORT"
echo "📁 Matrix World: $MATRIX_WORLD"
echo ""

# Start the server
python server.py \
    --matrix-world "$MATRIX_WORLD" \
    --host "$HOST" \
    --port "$PORT"
