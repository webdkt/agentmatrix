#!/bin/bash
# PPTX Screenshot Script wrapper
# Usage: scripts/screenshot.sh <input.pptx> [-o output_dir/] [-p pages]
# Examples:
#   scripts/screenshot.sh input.pptx -o screenshot/
#   scripts/screenshot.sh input.pptx -p 1,3,5 -o screenshot/
#   scripts/screenshot.sh input.pptx -p 2-6 -o screenshot/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCREENSHOT="$SCRIPT_DIR/pptd.py"

# Parse arguments
INPUT=""
OUTPUT="screenshots"
PAGES=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -p|--pages)
            PAGES="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Usage: $0 <input.pptx> [-o output_dir/] [-p pages]"
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
    echo "Usage: $0 <input.pptx> [-o output_dir/] [-p pages]"
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

# Build command
CMD=("$SCREENSHOT" screenshot "$INPUT" -o "$OUTPUT")

if [ -n "$PAGES" ]; then
    CMD+=(-p "$PAGES")
fi

# Run the screenshot script
python3 "${CMD[@]}"
