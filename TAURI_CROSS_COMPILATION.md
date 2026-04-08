# Tauri 跨平台编译架构特定二进制文件配置

## 🎯 问题描述

在 Tauri 跨平台编译时，Tauri 会自动寻找架构特定的二进制文件名：

```
resource path `binaries/server-x86_64-apple-darwin` doesn't exist
```

## 🔧 解决方案

### 1. 架构特定文件名映射

| 平台 | 架构特定文件名 | 通用文件名 |
|------|---------------|-----------|
| macOS ARM64 | `server-aarch64-apple-darwin` | `server` |
| macOS x64 | `server-x86_64-apple-darwin` | `server` |
| Windows x64 | `server-x86_64-pc-windows-msvc.exe` | `server.exe` |

### 2. GitHub Actions 构建脚本

```yaml
# macOS ARM
- name: Copy server to sidecar directory
  run: |
    mkdir -p agentmatrix-desktop/src-tauri/binaries
    # 复制架构特定文件名
    cp dist-server/server agentmatrix-desktop/src-tauri/binaries/server-aarch64-apple-darwin
    chmod +x agentmatrix-desktop/src-tauri/binaries/server-aarch64-apple-darwin
    # 同时保留通用文件名
    cp dist-server/server agentmatrix-desktop/src-tauri/binaries/server
    chmod +x agentmatrix-desktop/src-tauri/binaries/server

# macOS x64
- name: Copy server to sidecar directory
  run: |
    mkdir -p agentmatrix-desktop/src-tauri/binaries
    cp dist-server/server agentmatrix-desktop/src-tauri/binaries/server-x86_64-apple-darwin
    chmod +x agentmatrix-desktop/src-tauri/binaries/server-x86_64-apple-darwin
    cp dist-server/server agentmatrix-desktop/src-tauri/binaries/server
    chmod +x agentmatrix-desktop/src-tauri/binaries/server

# Windows
- name: Copy server to sidecar directory
  shell: bash
  run: |
    mkdir -p agentmatrix-desktop/src-tauri/binaries
    cp dist-server/server.exe agentmatrix-desktop/src-tauri/binaries/server-x86_64-pc-windows-msvc.exe
    cp dist-server/server.exe agentmatrix-desktop/src-tauri/binaries/server.exe
```

### 3. Tauri 配置文件

在 `tauri.conf.json` 中配置所有架构的二进制文件：

```json
{
  "bundle": {
    "externalBin": [
      "binaries/server",
      "binaries/server-aarch64-apple-darwin",
      "binaries/server-x86_64-apple-darwin",
      "binaries/server-x86_64-pc-windows-msvc.exe"
    ]
  }
}
```

## 🚀 工作原理

### Tauri 的二进制文件选择逻辑

1. **开发环境**：使用 `binaries/server` (通用文件名)
2. **本地构建**：使用当前平台对应的文件
3. **跨平台编译**：自动选择目标平台的架构特定文件名

### 构建流程

```mermaid
graph LR
    A[PyInstaller 构建] --> B[生成 server 可执行文件]
    B --> C[复制为架构特定文件名]
    C --> D[Tauri 打包]
    D --> E[生成平台特定安装包]
```

## 📋 验证方法

### 本地验证

```bash
# 检查 binaries 目录
ls -la agentmatrix-desktop/src-tauri/binaries/

# 应该看到类似输出：
# server
# server-aarch64-apple-darwin  (macOS ARM)
# server-x86_64-apple-darwin    (macOS x64)
```

### GitHub Actions 验证

1. 推送代码后检查 Actions 构建状态
2. 确认所有平台（macOS ARM/x64, Windows）都成功构建
3. 下载并测试生成的安装包

## ⚠️ 注意事项

### 1. 文件权限
确保复制的二进制文件有执行权限：
```bash
chmod +x agentmatrix-desktop/src-tauri/binaries/server*
```

### 2. 平台差异
- **Unix-like** (macOS/Linux): 无扩展名的可执行文件
- **Windows**: `.exe` 扩展名

### 3. 架构检测
Tauri 根据编译目标自动选择正确的二进制文件：
```rust
// Tauri 内部逻辑
match target_triple {
    "aarch64-apple-darwin" => "server-aarch64-apple-darwin",
    "x86_64-apple-darwin" => "server-x86_64-apple-darwin",
    "x86_64-pc-windows-msvc" => "server-x86_64-pc-windows-msvc.exe",
    _ => "server", // 通用文件名
}
```

## 🔍 故障排除

### 常见错误

1. **`resource path 'binaries/server-xxx' doesn't exist`**
   - 确保构建脚本复制了架构特定文件名
   - 检查文件权限设置

2. **`Permission denied`**
   - 确保二进制文件有执行权限
   - 在构建脚本中添加 `chmod +x`

3. **`Wrong ELF type`** (架构不匹配)
   - 确保跨平台编译时使用正确的工具链
   - macOS ARM runner 只能构建 ARM64 二进制文件

## 📚 相关资源

- [Tauri External Binaries](https://tauri.app/v1/guides/building/sidecar)
- [PyInstaller Cross-Compilation](https://pyinstaller.org/en/stable/spec-files.html)
- [GitHub Actions macOS Runners](https://github.com/actions/runner-images)

---

**总结**: 通过配置架构特定的二进制文件名，解决了 Tauri 跨平台编译时的文件查找问题，现在所有平台都能成功构建。
