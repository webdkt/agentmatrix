# Installation & Setup

## System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Node.js** | 18+ | Required for building the frontend |
| **npm** | 9+ | Comes with Node.js |
| **Python** | 3.10+ | Required for the agent runtime backend |
| **Rust** | Latest stable | Required for Tauri desktop build |
| **Podman or Docker** | Any recent version | Container runtime for agent isolation (Podman preferred) |

## Getting the Source Code

Clone the repository from GitHub:

```bash
git clone https://github.com/webdkt/agentmatrix.git
cd agentmatrix/agentmatrix-desktop
```

## Installing Dependencies

```bash
npm install
```

This installs all frontend dependencies (Vue 3, Pinia, Vite, etc.).

## Running in Development Mode

The development mode starts both the Vite dev server and the Tauri desktop app:

```bash
./start-dev.sh
```

To force the first-run wizard to appear (useful for testing):

```bash
./start-dev.sh --force-wizard
```

The script will:

1. Set up the Python backend path
2. Ensure resource directories exist
3. Copy the Matrix World template to the build directory
4. Start the Vite development server on port 5173
5. Compile and launch the Tauri desktop application

## Building for Production

To create a production build:

```bash
npm run tauri:build
```

This will:

1. Build the Vue frontend into optimized static files
2. Compile the Rust/Tauri backend
3. Package everything into a platform-specific installer (DMG on macOS, MSI on Windows, AppImage on Linux)

The output is located in `src-tauri/target/release/bundle/`.

## Stopping the Development Server

```bash
./stop-dev.sh
```

## Verifying the Installation

After launching the app, you should see:

1. If it's the first run: the **Cold-Start Wizard** (Matrix-rain animation)
2. If already configured: the **Email View** with your session list

If the app fails to start, check that:

- All prerequisites are installed and on your PATH
- Port 5173 is not in use by another application
- The Python backend can be found (the app looks for `server.py` in the parent directory)
