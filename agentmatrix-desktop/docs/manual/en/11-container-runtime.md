# Container Runtime

AgentMatrix uses container technology to run AI agents in isolated environments. This ensures security, consistency, and proper resource management.

## Supported Runtimes

| Runtime | Status | Notes |
|---------|--------|-------|
| **Podman** | Preferred | Rootless by default, better security posture |
| **Docker** | Supported | Widely available, fully compatible |

## Auto-Detection

On startup, AgentMatrix automatically detects which container runtime is available on your system:

1. Checks for **Podman** first
2. Falls back to **Docker** if Podman is not found
3. If neither is found, shows a notification

The detection order and fallback behavior can be configured in `matrix_config.yml`:

```yaml
container:
  runtime: "auto"        # "auto", "podman", or "docker"
  auto_start: true
  fallback_strategy: "fallback"
```

## macOS Setup

On macOS, AgentMatrix includes bundled Podman installer resources:

- Located in the app's resources directory
- Used when Podman is not installed on the system
- The app may prompt you to install Podman on first run

### Manual Podman Installation (macOS)

```bash
# Using Homebrew
brew install podman

# Initialize and start the Podman machine
podman machine init
podman machine start
```

## Windows Setup

On Windows, AgentMatrix can bundle Podman MSI installers. For manual installation:

1. Download Podman from the [official website](https://podman.io/)
2. Run the installer
3. Open a terminal and run `podman machine init` then `podman machine start`

Docker Desktop is also fully supported on Windows.

## Linux Setup

On Linux, install via your package manager:

```bash
# Debian/Ubuntu
sudo apt install podman

# Fedora
sudo dnf install podman

# Arch
sudo pacman -S podman
```

Docker is also widely available on Linux distributions.

## Verifying Container Runtime

To verify your container runtime is working:

```bash
# Check Podman
podman run hello-world

# Check Docker
docker run hello-world
```

If the hello-world container runs successfully, your runtime is properly configured.

## Why Containers?

AgentMatrix runs agents in containers for several reasons:

- **Isolation** — Each agent operates in its own environment, preventing interference
- **Security** — Agents cannot access your host filesystem directly (only through configured mounts)
- **Reproducibility** — Every agent gets a consistent runtime environment
- **Resource control** — Container resource limits prevent runaway processes
