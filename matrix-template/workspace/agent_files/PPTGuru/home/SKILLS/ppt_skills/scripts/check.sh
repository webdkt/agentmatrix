#!/bin/bash
# PPTD Checker wrapper script
# Usage: scripts/check.sh <pptd_file>
# Or from project root: bash scripts/check.sh path/to/file.pptd

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$SCRIPT_DIR/pptd.py"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <pptd_file>"
    exit 1
fi

PPTD_FILE="$1"

if [ ! -f "$PPTD_FILE" ]; then
    echo "Error: File not found: $PPTD_FILE"
    exit 1
fi

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

# Check if PyYAML is installed
python3 -c "import yaml" 2>/dev/null || {
    echo "Installing PyYAML..."
    pip3 install pyyaml 2>/dev/null || pip install pyyaml 2>/dev/null || {
        echo "Error: Failed to install PyYAML. Please install it manually: pip install pyyaml"
        exit 1
    }
}

# Run the checker
python3 "$CHECKER" check "$PPTD_FILE"
