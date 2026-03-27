# Chrome in Container

## 目标

让 Agent 能在自己的 Docker 容器内运行浏览器（Chromium + Playwright）。

## 改动清单

### 1. Dockerfile — 安装 Chromium

在现有镜像中加 Chromium 和字体依赖。镜像体积增加约 300-400MB。

### 2. requirements-docker.txt — 加 Python 依赖

加 `playwright` 和 `playwright-stealth`（不加 browser-use）。

### 3. 容器环境变量

- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium` — 让 playwright 自动使用系统 Chromium，不需要 `playwright install`
- Agent 写 `playwright.chromium.launch()` 即可

### 4. container_manager.py — X11 转发支持

在 `_create_container()` 中通过环境变量 `AGENTMATRIX_X11=true` 控制是否开启 X11 转发。

开启后的行为：

**Linux**：
- 挂载 `/tmp/.X11-unix` 到容器
- 设置 `DISPLAY=:0`
- 设置 `ipc_mode=host`（Chrome 共享内存需要）

**macOS（XQuartz）：
- 不挂载 `/tmp/.X11-unix`（macOS 上不存在）
- 自动执行 `xhost +localhost` 授权
- 设置 `DISPLAY=host.docker.internal:0`（通过 TCP 转发到 XQuartz）

### 5. XQuartz 打包（macOS full 版本）

- `tauri.conf.json` resources 数组加 `"resources/xquartz/**/*"`
- `build-desktop.yml` CI 下载 `XQuartz-2.8.5.pkg`（约 103MB）到 `resources/xquartz/`
- `main.rs` 加 `check_xquartz` / `install_xquartz` Tauri 命令

### 6. Agent 使用方式

Agent 在容器内通过 `file` skill 的 `bash` action 执行 playwright 脚本即可。Chromium 在 PATH 中，playwright 自动找到。

## 关于 --no-sandbox

容器内跑 Chromium 需要 `--no-sandbox` 启动参数。因为 Chrome 的沙箱需要 Linux 内核的 seccomp、user namespace 等能力，容器内默认没有。`--no-sandbox` 禁用 Chrome 自己的沙箱，信任容器的隔离。这个参数在 CI/CD 中广泛使用，没有废弃迹象。

## 关于反爬检测

容器浏览器可能被网站检测（User-Agent、WebGL 指纹、navigator.webdriver 等）。这不是容器特有的问题——宿主机无头浏览器也一样。可用 `playwright-stealth` 缓解。Agent 做研究、抓内容类场景，大部分网站不会拦。
