#!/bin/bash
#
# Build AgentMatrix Python backend with PyInstaller
# Usage: ./scripts/build-backend.sh [--output <dir>]
#
# This script:
# 1. Creates a virtual environment
# 2. Installs dependencies (without browser-use)
# 3. Builds the server executable with PyInstaller
# 4. Outputs to dist-server/server/

set -e

# Default output directory
OUTPUT_DIR="dist-server"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================"
echo "AgentMatrix Backend Builder"
echo "============================================"
echo ""

# Clean up previous build
if [ -d "dist-server" ]; then
    echo "Cleaning previous build..."
    rm -rf dist-server
fi
if [ -d "build" ]; then
    rm -rf build
fi

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m venv .build-venv

echo "Installing dependencies..."
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    source .build-venv/Scripts/activate
else
    source .build-venv/bin/activate
fi

pip install --upgrade pip
pip install pyinstaller

# Install requirements (skip browser-use)
echo "Installing project dependencies..."
grep -v "browser-use" requirements.txt > requirements-build.txt
pip install -r requirements-build.txt
rm requirements-build.txt

# Build with PyInstaller
echo "Building server with PyInstaller..."
pyinstaller server.spec --distpath "$OUTPUT_DIR" --clean

# Clean up venv
deactivate
rm -rf .build-venv

echo ""
echo "============================================"
echo "Build complete!"
echo "Server executable: $OUTPUT_DIR/server/server"
echo "============================================"
