# Troubleshooting

Common issues and their solutions.

## Application Won't Start

**Symptoms**: The app window doesn't appear, or crashes immediately.

**Solutions**:

- Verify all prerequisites are installed: Node.js 18+, Python 3.10+, Rust toolchain
- Check that port 5173 is not occupied by another application
- Try deleting `node_modules` and running `npm install` again
- Check the terminal output for specific error messages

## Backend Not Starting

**Symptoms**: The app launches but agents don't respond, or you see "Backend disconnected" status.

**Solutions**:

- Verify Python 3.10+ is installed and on your PATH: `python3 --version`
- Check that `auto_start_backend` is `true` in `~/.agentmatrix/settings.json`
- Try starting the backend manually to see error output
- Ensure the Matrix World directory exists and contains `.matrix/configs/`
- Check that `llm_config.json` exists in the configs directory

## WebSocket Disconnected

**Symptoms**: "Disconnected" status indicator, no real-time updates, new emails don't appear.

**Solutions**:

- Confirm the backend is running on port 8000
- Check your firewall or security software — it may block WebSocket connections
- Restart the application to force a reconnection
- The app automatically retries connection up to 5 times

## LLM Configuration Errors

**Symptoms**: Agents respond with errors, or the wizard fails at the model configuration step.

**Solutions**:

- Verify your API key is correct and has not expired
- Check the API base URL matches your provider's documentation
- Ensure the model name is spelled correctly (e.g., `gpt-4o`, not `GPT-4`)
- Test the API key with a direct curl request to the provider
- For custom endpoints, ensure the server is running and accessible

## Podman / Docker Not Found

**Symptoms**: Warning about container runtime not available.

**Solutions**:

- Install Podman (preferred) or Docker on your system
- On macOS, run `podman machine init && podman machine start`
- Verify the installation: `podman --version` or `docker --version`
- Restart AgentMatrix after installing the container runtime

## Email Proxy Connection Failed

**Symptoms**: "Test Connection" fails in Email Proxy settings.

**Solutions**:

- Double-check IMAP/SMTP hostnames and ports
- For Gmail, use an App Password instead of your regular password
- Ensure your email provider allows IMAP/SMTP access (some providers require it to be enabled in settings)
- Check if your network blocks the required ports (993 for IMAP, 587 for SMTP)
- Try connecting with a desktop email client (e.g., Thunderbird) to verify credentials

## Notifications Not Appearing

**Symptoms**: No desktop notifications when new emails arrive.

**Solutions**:

- Check that `enable_notifications` is `true` in `~/.agentmatrix/settings.json`
- Grant notification permissions to AgentMatrix in your OS settings
- On macOS: System Preferences > Notifications > AgentMatrix
- On Windows: Settings > System > Notifications > AgentMatrix

## Configuration File Corruption

**Symptoms**: App fails to start or behaves unexpectedly after manual config edits.

**Solutions**:

- Validate YAML files for syntax errors (proper indentation, no tabs)
- Validate JSON files (matching brackets, proper quoting)
- Restore from backup or delete the file to trigger default values
- As a last resort, delete `~/.agentmatrix/settings.json` to re-run the wizard
