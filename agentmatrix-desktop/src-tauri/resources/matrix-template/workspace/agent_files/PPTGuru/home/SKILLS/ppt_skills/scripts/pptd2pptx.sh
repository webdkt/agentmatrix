#!/bin/bash
# PPTD to PPTX Converter wrapper script
# Usage: scripts/pptd2pptx.sh <input.pptd> [-o output.pptx]
# Or from project root: bash scripts/pptd2pptx.sh output/anomaly_detection_platform/presentation.pptd

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERTER="$SCRIPT_DIR/pptd.py"

# Parse arguments
INPUT=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Usage: $0 <input.pptd> [-o output.pptx]"
            exit 1
            ;;
        *)
            if [ -z "$INPUT" ]; then
                INPUT="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$INPUT" ]; then
    echo "Usage: $0 <input.pptd> [-o output.pptx]"
    exit 1
fi

if [ ! -f "$INPUT" ]; then
    echo "Error: Input file not found: $INPUT"
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

# Check if python-pptx is installed
python3 -c "import pptx" 2>/dev/null || {
    echo "Installing python-pptx..."
    pip3 install python-pptx 2>/dev/null || pip install python-pptx 2>/dev/null || {
        echo "Error: Failed to install python-pptx. Please install it manually: pip install python-pptx"
        exit 1
    }
}

# Determine output path if not specified
if [ -z "$OUTPUT" ]; then
    OUTPUT="${INPUT%.pptd}.pptx"
fi

# Run the converter
echo "Converting: $INPUT -> $OUTPUT"
python3 "$CONVERTER" export "$INPUT" -o "$OUTPUT"
