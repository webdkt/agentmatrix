# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AgentMatrix Server

Build command:
  pyinstaller server.spec

Output:
  dist/server (macOS/Linux) or dist/server.exe (Windows)
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Project root
project_root = Path(os.getcwd())

a = Analysis(
    ['server.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Include the entire agentmatrix package (all submodules, including skills)
        ('src/agentmatrix', 'agentmatrix'),
    ],
    # Note: All agentmatrix submodules are included via the datas directive above
    # PyInstaller will analyze Python imports and bundle dependencies automatically
    hiddenimports=[
        # FastAPI and related
        'fastapi',
        'uvicorn',
        'websockets',
        'multipart',
        'multipart.multipart',

        # YAML
        'yaml',

        # HTTP
        'aiohttp',
        'aiohttp.client',
        'requests',
        'requests.exceptions',

        # Browser dependencies
        'DrissionPage',
        'DrissionPage._pages',
        'DrissionPage._configs',
        'DrissionPage._functions',

        # PDF processing
        'marker',
        'marker_pdf',
        'fitz',  # PyMuPDF
        'html2text',
        'trafilatura',
        'bs4',  # beautifulsoup4 package name

        # Jinja2
        'jinja2',
        'jinja2.environment',

        # Pydantic
        'pydantic',
        'pydantic.fields',

        # Podman
        'podman',
        'podman.client',
        'podman.errors',
        'podman.compat',

        # tmux
        'libtmux',

        # email
        'imap_tools',
        'smtplib',
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',

        # Other
        'dotenv',
        'aioconsole',
        'markdown_it',
        'markdown_it.renderer',
        'sqlite3',
        'pathlib',

        # Skills module (dynamic loading support)
        'agentmatrix.skills',
        'agentmatrix.skills.registry',

        # Skills that use dynamic imports (ensure they're included in PyInstaller)
        # These modules are loaded dynamically via importlib.util.spec_from_file_location
        # We list them here to ensure PyInstaller includes them in the bundle
        'agentmatrix.skills.base',
        'agentmatrix.skills.file_skill',
        'agentmatrix.skills.new_web_search',
        'agentmatrix.skills.memory',
        'agentmatrix.skills.markdown',
        'agentmatrix.skills.agent_admin',
        'agentmatrix.skills.system_admin',
        'agentmatrix.skills.email',
        'agentmatrix.skills.scheduler',
        'agentmatrix.skills.deep_researcher',

        # Importlib (for dynamic skill loading)
        'importlib.util',
        'importlib.machinery',
    ],
    excludes=[
        # Exclude browser-use (not needed)
        'browser_use',
        'browser_use.agent',
        'browser_use.controller',
        'browser_use.controller.service',
        'browser_use.browser',
        'browser_use.browser.browser',
        'langchain',
        'langchain_openai',
        'langchain_core',
        'langchain_community',
        'openai',

        # Exclude tkinter
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',

        # Exclude matplotlib (not used)
        'matplotlib',

        # Exclude IPython (not used)
        'IPython',
        'ipykernel',

        # Exclude Jupyter
        'jupyter',
        'notebook',
        'nbconvert',

        # Exclude test frameworks
        'pytest',
        'unittest',
        'nose',

        # Exclude dev tools
        'black',
        'flake8',
        'mypy',
        'ruff',

        # Exclude heavy optional dependencies
        'numpy',
        'pandas',
        'scipy',
        'sklearn',
        'torch',
        'tensorflow',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use onedir mode for fast startup (no extraction needed)
# All dependencies are in a folder alongside the executable
exe = EXE(
    pyz,
    a.scripts,
    [],  # Exclude binaries, zipfiles, datas from EXE (onedir mode)
    exclude_binaries=True,  # Important: don't bundle binaries into EXE
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# COLLECT: collect all binaries, datas, and the EXE into a folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='server',  # Folder name will be 'server'
)
