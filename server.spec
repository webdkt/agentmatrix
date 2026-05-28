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


# === Dynamically collect all agentmatrix submodules ===
def collect_agentmatrix_hiddenimports():
    """
    Walk src/agentmatrix/ and generate hidden import paths for every .py module.
    This ensures PyInstaller knows about all submodules after the package restructuring.
    """
    src_dir = project_root / "src" / "agentmatrix"
    modules = []
    if not src_dir.exists():
        print(f"WARNING: {src_dir} does not exist, skipping hidden imports collection")
        return modules

    for root, dirs, files in os.walk(str(src_dir)):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"):
                continue
            filepath = Path(root) / f
            rel = filepath.relative_to(src_dir)
            parts = list(rel.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            module_path = "agentmatrix." + ".".join(parts) if parts else "agentmatrix"
            modules.append(module_path)

    return sorted(set(modules))


agentmatrix_hiddenimports = collect_agentmatrix_hiddenimports()
print(f"Collected {len(agentmatrix_hiddenimports)} agentmatrix hidden imports")

a = Analysis(
    ['server.py'],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=[],
    datas=[
        # Include the entire agentmatrix package (all submodules, including skills)
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
        'aiosqlite',
        'pathlib',

        # === server_handlers modules (refactored from server.py) ===
        'server_handlers',
        'server_handlers.state',
        'server_handlers.models',
        'server_handlers.lifecycle',
        'server_handlers.utils',
        'server_handlers.app_factory',
        'server_handlers.routes',
        'server_handlers.routes.system',
        'server_handlers.routes.websocket',
        'server_handlers.routes.config',
        'server_handlers.routes.sessions',
        'server_handlers.routes.agents',
        'server_handlers.routes.agent_profiles',
        'server_handlers.routes.skills',
        'server_handlers.routes.llm_configs',
        'server_handlers.routes.email_proxy',
        'server_handlers.routes.proxy',

        # === agentmatrix modules (auto-collected from src/agentmatrix/) ===
        # These are dynamically collected above to stay in sync with package restructuring.
        # Skills use dynamic loading (importlib.util.spec_from_file_location),
        # so PyInstaller's static analysis cannot discover them automatically.
        *agentmatrix_hiddenimports,

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
