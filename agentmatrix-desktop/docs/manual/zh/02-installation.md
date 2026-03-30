# 安装与设置

## 系统要求

| 要求 | 版本 | 说明 |
|------|------|------|
| **Node.js** | 18+ | 构建前端所必需 |
| **npm** | 9+ | 随 Node.js 附带 |
| **Python** | 3.10+ | 智能体运行时后端所必需 |
| **Rust** | 最新稳定版 | Tauri 桌面构建所必需 |
| **Podman 或 Docker** | 任意近期版本 | 容器运行时，用于智能体隔离（推荐 Podman） |

## 获取源代码

从 GitHub 克隆仓库：

```bash
git clone https://github.com/webdkt/agentmatrix.git
cd agentmatrix/agentmatrix-desktop
```

## 安装依赖

```bash
npm install
```

此命令会安装所有前端依赖（Vue 3、Pinia、Vite 等）。

## 开发模式运行

开发模式会同时启动 Vite 开发服务器和 Tauri 桌面应用：

```bash
./start-dev.sh
```

强制显示首次运行向导（用于测试）：

```bash
./start-dev.sh --force-wizard
```

脚本会执行以下步骤：

1. 设置 Python 后端路径
2. 确保资源目录存在
3. 将 Matrix World 模板复制到构建目录
4. 在 5173 端口启动 Vite 开发服务器
5. 编译并启动 Tauri 桌面应用

## 生产环境构建

创建生产构建：

```bash
npm run tauri:build
```

此命令会：

1. 将 Vue 前端构建为优化的静态文件
2. 编译 Rust/Tauri 后端
3. 打包为平台特定的安装包（macOS 为 DMG，Windows 为 MSI，Linux 为 AppImage）

输出位于 `src-tauri/target/release/bundle/` 目录。

## 停止开发服务器

```bash
./stop-dev.sh
```

## 验证安装

启动应用后，您应该看到：

1. 如果是首次运行：**冷启动向导**（Matrix 雨动画）
2. 如果已配置：**邮件视图**，显示会话列表

如果应用启动失败，请检查：

- 所有前置条件是否已安装并在 PATH 中
- 5173 端口是否未被其他应用占用
- Python 后端是否可被找到（应用会在上级目录查找 `server.py`）
