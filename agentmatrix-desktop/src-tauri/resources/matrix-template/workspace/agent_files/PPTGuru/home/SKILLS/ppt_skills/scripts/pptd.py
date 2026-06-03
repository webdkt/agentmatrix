#!/usr/bin/env python3
"""
PPTD Toolkit — Unified CLI for PPTD format operations.

Usage:
    python3 pptd.py convert  <input.pptx> [-o output_dir/]
    python3 pptd.py check    <input.pptd>
    python3 pptd.py export   <input.pptd> [-o output.pptx]
    python3 pptd.py screenshot <input.pptx> [-o output_dir/] [-p pages]
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure script directory is on the import path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))


def cmd_convert(args):
    from pptd_convert import convert_pptx_to_pptd
    convert_pptx_to_pptd(args.input, args.output)


def cmd_check(args):
    from pptd_check import PPTDChecker
    checker = PPTDChecker(args.input)
    checker.run()


def cmd_export(args):
    from pptd_export import convert_pptd_to_pptx
    output = args.output or str(Path(args.input).with_suffix('.pptx'))
    convert_pptd_to_pptx(args.input, output)


def cmd_screenshot(args):
    from pptd_screenshot import generate_screenshots
    generate_screenshots(args.input, args.output, args.pages)


def main():
    parser = argparse.ArgumentParser(
        prog='pptd',
        description='PPTD Toolkit — convert, check, export, and screenshot PowerPoint presentations',
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # convert: PPTX -> PPTD
    p_convert = subparsers.add_parser('convert', help='Convert PPTX to PPTD format')
    p_convert.add_argument('input', help='Input .pptx file')
    p_convert.add_argument('-o', '--output', default='.', help='Output directory (default: .)')

    # check: validate PPTD
    p_check = subparsers.add_parser('check', help='Validate PPTD files for errors and warnings')
    p_check.add_argument('input', help='Input .pptd file')

    # export: PPTD -> PPTX
    p_export = subparsers.add_parser('export', help='Export PPTD to PPTX format')
    p_export.add_argument('input', help='Input .pptd file')
    p_export.add_argument('-o', '--output', help='Output .pptx file (default: input.pptx)')

    # screenshot: PPTX screenshots
    p_screenshot = subparsers.add_parser('screenshot', help='Generate page screenshots from PPTX')
    p_screenshot.add_argument('input', help='Input .pptx file')
    p_screenshot.add_argument('-o', '--output', default='screenshots', help='Output directory (default: screenshots/)')
    p_screenshot.add_argument('-p', '--pages', help='Page numbers to capture (e.g., "1,3,5" or "2-6")')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        'convert': cmd_convert,
        'check': cmd_check,
        'export': cmd_export,
        'screenshot': cmd_screenshot,
    }

    try:
        commands[args.command](args)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error during {args.command}: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
