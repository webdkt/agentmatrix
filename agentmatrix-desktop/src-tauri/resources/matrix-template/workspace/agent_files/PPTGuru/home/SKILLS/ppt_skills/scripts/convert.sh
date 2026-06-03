#!/bin/bash
# PPTX to PPTD Converter wrapper script
# Usage: scripts/convert.sh <input.pptx> [-o output_dir/]
# Or from project root: bash scripts/convert.sh input.pptx -o output/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERTER="$SCRIPT_DIR/pptd.py"

# Parse arguments
INPUT=""
OUTPUT="."

while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Usage: $0 <input.pptx> [-o output_dir/]"
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
    echo "Usage: $0 <input.pptx> [-o output_dir/]"
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

# Run the converter
python3 "$CONVERTER" convert "$INPUT" -o "$OUTPUT"
