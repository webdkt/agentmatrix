# D2 安装指南

本文档提供了在各种操作系统上安装 D2 的详细指南。

## 检查是否已安装

在开始之前，先检查 D2 是否已经安装：

```bash
d2 --version
```

如果显示了版本信息，说明 D2 已经安装，可以直接使用。

如果没有安装，请按照以下步骤进行安装。

## 安装方法

### 方法 1：官方安装脚本（推荐）

适用于 Linux、macOS 和 Windows (WSL)：

```bash
curl -fsSL https://d2lang.com/install.sh | sh -s --
```

或者先预览安装脚本会执行的操作：

```bash
curl -fsSL https://d2lang.com/install.sh | sh -s -- --dry-run
```

安装完成后，验证安装：

```bash
d2 --version
```

### 方法 2：使用 Go 安装

如果你已经安装了 Go：

```bash
go install oss.terrastruct.com/d2@latest
```

确保 `$GOPATH/bin` 在你的 `PATH` 中：

```bash
export PATH=$PATH:$(go env GOPATH)/bin
```

### 方法 3：使用包管理器

#### macOS (Homebrew)

```bash
brew install d2
```

#### Linux (各种发行版)

**Ubuntu/Debian:**
```bash
# 添加 D2 仓库
sudo curl -fsSL https://d2lang.com/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/d2.gpg
echo "deb [signed-by=/usr/share/keyrings/d2.gpg] https://releases.d2lang.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/d2.list

# 安装
sudo apt update
sudo apt install d2
```

**Fedora:**
```bash
sudo dnf install d2
```

**Arch Linux:**
```bash
yay -S d2
```

#### Windows

**使用 Chocolatey:**
```powershell
choco install d2
```

**使用 Scoop:**
```powershell
scoop install d2
```

**使用 WSL:**
在 WSL 中使用官方安装脚本：
```bash
curl -fsSL https://d2lang.com/install.sh | sh -s --
```

### 方法 4：从源码编译

如果你需要从源码编译：

```bash
# 克隆仓库
git clone https://github.com/terrastruct/d2.git
cd d2

# 编译
make build

# 安装
sudo make install
```

## 验证安装

安装完成后，验证 D2 是否正确安装：

```bash
d2 --version
```

你应该看到类似这样的输出：
```
D2 - A modern diagram scripting language
Version: vX.X.X
```

## 测试 D2

创建一个简单的测试文件：

```bash
# 创建测试文件
echo 'x -> y -> z' > test.d2

# 生成图表
d2 test.d2 test.svg
```

## 升级 D2

### 使用官方安装脚本

```bash
curl -fsSL https://d2lang.com/install.sh | sh -s --
```

### 使用 Go

```bash
go install oss.terrastruct.com/d2@latest
```

### 使用包管理器

```bash
# macOS
brew upgrade d2

# Ubuntu/Debian
sudo apt update && sudo apt upgrade d2

# Chocolatey
choco upgrade d2
```

## 卸载 D2

### 使用官方安装脚本

```bash
curl -fsSL https://d2lang.com/install.sh | sh -s -- --uninstall
```

### 使用包管理器

```bash
# macOS
brew uninstall d2

# Ubuntu/Debian
sudo apt remove d2

# Chocolatey
choco uninstall d2
```

### 手动卸载

```bash
# 查找 D2 可执行文件
which d2

# 删除可执行文件
sudo rm $(which d2)

# 删除配置文件（可选）
rm -rf ~/.config/d2
```

## 故障排除

### 问题 1：命令未找到

**症状**：运行 `d2 --version` 时显示 "command not found"

**解决方案**：
1. 确认 D2 已正确安装
2. 检查 `$PATH` 环境变量
3. 尝试重启终端

```bash
# 查找 D2 安装位置
find /usr -name d2 2>/dev/null

# 添加到 PATH
export PATH=$PATH:/path/to/d2
```

### 问题 2：权限错误

**症状**：安装时出现权限错误

**解决方案**：
```bash
# 使用 sudo 安装
sudo curl -fsSL https://d2lang.com/install.sh | sh -s --
```

### 问题 3：版本过旧

**症状**：D2 已安装但版本过旧

**解决方案**：
```bash
# 升级到最新版本
curl -fsSL https://d2lang.com/install.sh | sh -s --
```

### 问题 4：在 Windows 上无法使用

**解决方案**：
1. 使用 WSL（推荐）
2. 使用 Chocolatey 或 Scoop
3. 下载预编译的二进制文件

## 下一步

安装完成后，你可以：

1. 阅读 [quick-start.md](./quick-start.md) 快速入门
2. 查看 [SYNTAX.md](./SYNTAX.md) 学习 D2 语法
3. 浏览 [examples/](./examples/) 目录中的示例
4. 创建你的第一个图表！

## 获取帮助

如果遇到问题：

1. 查看 D2 官方文档：https://d2lang.com
2. 访问 D2 GitHub：https://github.com/terrastruct/d2
3. 加入 D2 Discord：https://discord.gg/NF6X8K4eDq
4. 提交问题：https://github.com/terrastruct/d2/issues

## 系统要求

- **操作系统**：Linux、macOS、Windows (WSL)
- **架构**：x86_64、ARM64
- **依赖**：无特殊依赖

D2 是一个独立的二进制文件，不需要额外的依赖或运行时环境。

## 安装位置

不同安装方法的安装位置：

- **官方脚本**：`/usr/local/bin/d2`
- **Go install**：`$(go env GOPATH)/bin/d2`
- **Homebrew**：`/usr/local/bin/d2` 或 `/opt/homebrew/bin/d2`
- **apt**：`/usr/bin/d2`

## 环境变量

D2 支持以下环境变量：

```bash
# 设置 D2 可执行文件路径
export D2_BIN=/path/to/d2

# 设置默认主题
export D2_DEFAULT_THEME=300

# 设置默认布局引擎
export D2_DEFAULT_LAYOUT=elk
```

## 总结

D2 的安装非常简单，推荐使用官方安装脚本：

```bash
curl -fsSL https://d2lang.com/install.sh | sh -s --
```

安装完成后，你就可以开始创建漂亮的图表了！

**提示**：参考 [SYNTAX.md](./SYNTAX.md) 和 [EXAMPLES.md](./EXAMPLES.md) 是学习 D2 的最佳方式。
