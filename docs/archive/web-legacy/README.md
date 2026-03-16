# AgentMatrix Legacy Web Application - Archive

## ⚠️ **DEPRECATED**

This web application has been **archived and is no longer maintained**.

**Migration Date**: 2026-03-16
**Replaced By**: AgentMatrix Desktop Application (`agentmatrix-desktop/`)

## 📋 Archive Information

### What was this?

The legacy web application was the original browser-based interface for AgentMatrix, built with:
- **Alpine.js** - Lightweight reactive framework
- **Tailwind CSS** - Utility-first CSS framework
- **Single Page Application** - All functionality in `index.html`

### Why was it replaced?

1. **Modern Architecture**: The new desktop app uses Vue 3 + Vite for better developer experience
2. **Desktop Integration**: Tauri enables native desktop features (system tray, notifications, etc.)
3. **Better Performance**: Modern build tools and optimization
4. **Enhanced UX**: Improved user interface and experience

### Migration Path

**Old Web Application → New Desktop Application**

| Old Location | New Location |
|-------------|-------------|
| `http://localhost:8000` | Desktop app (Tauri) |
| `web/` directory | `agentmatrix-desktop/` |
| Alpine.js components | Vue 3 components |
| Direct browser access | Native desktop application |

## 🗂️ Original Features

The legacy web application provided:

- ✉️ Email-style interaction interface
- 🤖 Multi-agent collaboration management
- 📊 Real-time session monitoring
- 📝 Agent configuration wizards
- 📈 Performance metrics and logging

## 📦 Backup Information

**Original Location**: `/Users/dkt/myprojects/agentmatrix/web/`
**Backup Tag**: `checkpoint-phase0-start`
**Archive Date**: 2026-03-16

### Files in Archive

```
web/
├── index.html           # Main SPA (122KB)
├── css/                 # Custom styles
├── js/                  # JavaScript modules
│   ├── app.js          # Main application logic
│   ├── agents.js       # Agent management
│   ├── sessions.js     # Session management
│   ├── emails.js       # Email interface
│   └── settings.js     # Settings panel
├── libs/               # Third-party libraries
├── matrix_template/    # Configuration templates
└── README.md           # Original documentation
```

## 🔄 How to Access Legacy Version

If you need to access the legacy web application:

```bash
# Checkout the backup tag
git checkout checkpoint-phase0-start

# Start the server
python server.py

# Access at http://localhost:8000
```

**Warning**: The legacy version is not maintained and may not work with current backend APIs.

## 📚 Reference Documentation

For the current application, see:
- **Desktop App**: `agentmatrix-desktop/README.md`
- **Installation**: `docs/user/guide/installation.md`
- **API Documentation**: `http://localhost:8000/docs` (when server is running)

## ⚙️ Technical Details

### Technology Stack (Legacy)

- **Frontend Framework**: Alpine.js 3.x
- **Styling**: Tailwind CSS 3.x
- **Build**: No build process (direct browser execution)
- **API Communication**: WebSocket + REST
- **Markdown Rendering**: Marked.js

### Known Issues

- No modern build optimization
- Limited type safety
- Manual dependency management
- No hot module replacement
- Limited tooling support

## 🚫 Deprecation Timeline

- **2026-03-16**: Official deprecation
- **2026-03-16**: Archive created
- **Future**: Security updates only (if critical)

## 💡 Migration Guide for Users

If you were using the legacy web application:

1. **Install the Desktop Application**:
   ```bash
   cd agentmatrix-desktop
   npm install
   npm run tauri:dev
   ```

2. **Your Data is Safe**:
   - All configurations remain in `MatrixWorld/.matrix/`
   - No data migration needed
   - Desktop app uses the same backend

3. **New Features**:
   - Native desktop integration
   - System tray support
   - Native notifications
   - Better performance

## 📞 Support

For issues or questions:
- Use the desktop application instead
- Check `agentmatrix-desktop/README.md`
- Report issues at GitHub Issues

---

*This archive is maintained for historical reference only.*
*Last Updated: 2026-03-16*
