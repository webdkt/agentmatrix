#!/usr/bin/env python3
"""
PPTD Screenshot — generates page screenshots from PPTX files.
Usage: python3 pptd_screenshot.py <input.pptx> [-o output_dir/] [-p pages]
"""

import sys
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def check_command(cmd):
    return shutil.which(cmd) is not None


def convert_pptx_to_pdf(pptx_path, output_pdf):
    if not check_command('soffice') and not check_command('libreoffice'):
        print('Error: LibreOffice (soffice/libreoffice) is not installed.')
        print('  macOS: brew install --cask libreoffice')
        print('  Ubuntu/Debian: sudo apt-get install libreoffice')
        sys.exit(1)

    cmd_name = 'soffice' if check_command('soffice') else 'libreoffice'

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f'Converting PPTX to PDF using {cmd_name}...')
        result = subprocess.run(
            [cmd_name, '--headless', '--convert-to', 'pdf', '--outdir', tmpdir, str(pptx_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f'Error converting to PDF: {result.stderr}')
            sys.exit(1)

        pdf_files = list(Path(tmpdir).glob('*.pdf'))
        if not pdf_files:
            print('Error: PDF was not generated')
            sys.exit(1)

        shutil.move(str(pdf_files[0]), output_pdf)
        print(f'PDF generated: {output_pdf}')


def pdf_to_images(pdf_path, output_dir, pages=None):
    if not check_command('pdftoppm') and not check_command('convert'):
        print('Error: Neither pdftoppm (poppler) nor ImageMagick (convert) is available.')
        print('  pdftoppm: brew install poppler (macOS) or apt-get install poppler-utils')
        print('  ImageMagick: brew install imagemagick (macOS) or apt-get install imagemagick')
        sys.exit(1)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if check_command('pdftoppm'):
        print('Converting PDF to images using pdftoppm...')
        cmd = ['pdftoppm', '-png', '-r', '150', str(pdf_path), str(output_dir / 'page')]
        if pages:
            for start, end in parse_page_ranges(pages):
                cmd.extend(['-f', str(start), '-l', str(end)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'Error converting PDF: {result.stderr}')
            sys.exit(1)

        for f in sorted(output_dir.glob('page-*.png')):
            parts = f.stem.split('-')
            if len(parts) >= 2:
                page_num = int(parts[-1])
                new_name = output_dir / f'page_{page_num:03d}.png'
                f.rename(new_name)

    elif check_command('convert'):
        print('Converting PDF to images using ImageMagick...')
        result = subprocess.run(['identify', str(pdf_path)], capture_output=True, text=True)
        if result.returncode != 0:
            print(f'Error identifying PDF: {result.stderr}')
            sys.exit(1)

        total_pages = len(result.stdout.strip().split('\n'))
        page_ranges = parse_page_ranges(pages) if pages else [(1, total_pages)]

        for start, end in page_ranges:
            for page_num in range(start, end + 1):
                input_spec = f'{pdf_path}[{page_num - 1}]'
                output_file = output_dir / f'page_{page_num:03d}.png'
                result = subprocess.run(
                    ['convert', '-density', '150', input_spec, '-quality', '100', str(output_file)],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    print(f'Warning: Failed to convert page {page_num}: {result.stderr}')
                else:
                    print(f'  Generated: {output_file.name}')


def parse_page_ranges(pages_str):
    ranges = []
    for part in pages_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            ranges.append((int(start.strip()), int(end.strip())))
        else:
            page = int(part.strip())
            ranges.append((page, page))
    return ranges


def generate_screenshots(input_path, output_dir='screenshots', pages=None):
    """Generate screenshots from a PPTX or PPTD file."""
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')

    # If input is .pptd, convert to .pptx first
    if input_path.suffix == '.pptd':
        print('Input is .pptd, converting to .pptx first...')
        from pptd_export import convert_pptd_to_pptx
        tmp_pptx = Path(tempfile.mkdtemp()) / f'{input_path.stem}.pptx'
        convert_pptd_to_pptx(str(input_path), str(tmp_pptx))
        input_path = tmp_pptx

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / 'temp.pdf'
        convert_pptx_to_pdf(input_path, pdf_path)
        pdf_to_images(pdf_path, output_dir, pages)

    print(f'\nScreenshot generation complete!')
    print(f'  Output directory: {output_dir}')
    files = sorted(output_dir.glob('page_*.png'))
    print(f'  Generated {len(files)} screenshots')
    for f in files:
        print(f'    {f.name}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate screenshots from PPTX/PPTD files')
    parser.add_argument('input', help='Input .pptx or .pptd file')
    parser.add_argument('-o', '--output', default='screenshots', help='Output directory')
    parser.add_argument('-p', '--pages', help='Page numbers (e.g., "1,3,5" or "2-6")')
    args = parser.parse_args()
    generate_screenshots(args.input, args.output, args.pages)
