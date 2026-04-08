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
        # Include the entire agentmatrix package
        ('src/agentmatrix', 'agentmatrix'),
    ],
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

        # AgentMatrix core (PyInstaller usually finds these automatically)
        'agentmatrix',

        # Skills are loaded dynamically via importlib.import_module
        'agentmatrix.skills.base',
        'agentmatrix.skills.email',
        'agentmatrix.skills.file',
        'agentmatrix.skills.agent_admin',
        'agentmatrix.skills.system_admin',
        'agentmatrix.skills.deep_researcher',

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

# Use onefile mode for single-file executable (easier for Tauri sidecar)
# All dependencies are bundled into the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # Include binaries in the EXE (onefile mode)
    a.zipfiles,
    a.datas,     # Include data files in the EXE (onefile mode)
    [],
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
