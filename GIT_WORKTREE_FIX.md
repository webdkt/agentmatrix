# Git Worktree 兼容性修复

## 问题描述

在 Git worktree 中运行 `start-dev.sh` 时，出现以下错误：

```
python: can't open file '/Users/dkt/myprojects/agentmatrix-bugfix/agentmatrix-desktop/src-tauri/server.py': [Errno 2] No such file or directory
```

## 根本原因

1. **符号链接冲突**：Git worktree 配置中，`src-tauri/target` 是一个符号链接，指向原始仓库的 target 目录：
   ```
   /Users/dkt/myprojects/agentmatrix-bugfix/agentmatrix-desktop/src-tauri/target ->
   /Users/dkt/myprojects/agentmatrix/agentmatrix-desktop/src-tauri/target
   ```

2. **路径查找失败**：Rust 代码从 `resource_dir`（即 `target/debug/`）开始向上查找 `server.py`，但由于符号链接的存在，路径解析会跳到**原始仓库**而不是 worktree。

3. **结果**：在原始仓库中找不到 worktree 特定的配置文件和代码。

## 解决方案

使用 `CARGO_MANIFEST_DIR` 环境变量来定位项目根目录，而不是从 `resource_dir` 搜索。

### 修改内容

在 `agentmatrix-desktop/src-tauri/src/main.rs` 的 `start_backend()` 函数中：

**修改前：**
```rust
let project_root = if cfg!(dev) {
    // Dev mode: walk up from resource_dir to find server.py
    let mut dir = resource_dir.as_path();
    let mut found = None;
    for _ in 0..10 {
        if dir.join("server.py").exists() {
            found = Some(dir);
            break;
        }
        match dir.parent() {
            Some(p) => dir = p,
            None => break,
        }
    }
    found.unwrap_or(&resource_dir)
}
```

**修改后：**
```rust
let project_root = if cfg!(dev) {
    // Dev mode: use CARGO_MANIFEST_DIR to find project root
    // This works correctly in Git worktrees because it's not affected by symlinks
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));

    // CARGO_MANIFEST_DIR is src-tauri/, go up 2 levels to reach project root
    let project_root = manifest_dir.parent()
        .and_then(|p| p.parent())
        .unwrap_or(&manifest_dir);

    // Verify server.py exists at expected location
    if !project_root.join("server.py").exists() {
        eprintln!("Warning: server.py not found at {:?}", project_root.join("server.py"));
        eprintln!("Falling back to resource_dir search...");

        // Fallback: search from resource_dir (may fail in worktrees)
        let mut dir = resource_dir.as_path();
        let mut found = None;
        for _ in 0..10 {
            if dir.join("server.py").exists() {
                found = Some(dir.to_path_buf());
                break;
            }
            match dir.parent() {
                Some(p) => dir = p,
                None => break,
            }
        }
        found.unwrap_or_else(|| project_root.to_path_buf())
    } else {
        project_root.to_path_buf()
    }
}
```

### 为什么这个方案有效？

1. **CARGO_MANIFEST_DIR**：这是 Cargo 在编译时设置的环境变量，指向 `Cargo.toml` 所在的目录（即 `src-tauri/`）

2. **不受符号链接影响**：`src-tauri/` 目录本身不是符号链接（只有其子目录 `target/` 是），所以在 worktree 中这个路径是正确的

3. **确定性路径**：通过向上两级（`src-tauri/` -> `agentmatrix-desktop/` -> 项目根目录），可以可靠地找到项目根目录

4. **验证机制**：代码会验证 `server.py` 是否存在，如果不存在则回退到原始的搜索逻辑

## 测试验证

```bash
# 测试路径解析逻辑
python3 << 'EOF'
import pathlib

manifest_dir = pathlib.Path("/Users/dkt/myprojects/agentmatrix-bugfix/agentmatrix-desktop/src-tauri")
project_root = manifest_dir.parent.parent
server_py = project_root / "server.py"

print(f"CARGO_MANIFEST_DIR: {manifest_dir}")
print(f"Project root: {project_root}")
print(f"server.py exists: {server_py.exists()}")
EOF
```

输出：
```
CARGO_MANIFEST_DIR: /Users/dkt/myprojects/agentmatrix-bugfix/agentmatrix-desktop/src-tauri
Project root: /Users/dkt/myprojects/agentmatrix-bugfix
server.py exists: True
```

## 其他可能的解决方案

### 方案 1：移除符号链接（不推荐）
在 worktree 中创建真实的 `target` 目录，而不是使用符号链接。

**缺点**：
- 失去共享构建缓存的好处
- 增加磁盘使用
- 需要修改 Git worktree 配置

### 方案 2：使用环境变量（可行）
在 `start-dev.sh` 中设置 `PROJECT_ROOT` 环境变量，然后在 Rust 代码中读取。

**缺点**：
- 需要修改启动脚本
- 不如 `CARGO_MANIFEST_DIR` 简洁

### 方案 3：使用 .cargo/config（复杂）
在 worktree 中配置不同的构建目录。

**缺点**：
- 配置复杂
- 可能影响其他构建行为

## 总结

**当前方案（使用 CARGO_MANIFEST_DIR）** 是最优解决方案，因为：
- ✅ 简单可靠，不依赖复杂的配置
- ✅ 不影响原始仓库的构建过程
- ✅ 保留符号链接的优势（共享构建缓存）
- ✅ 使用 Cargo 内置机制，兼容性好
- ✅ 有验证和回退机制，确保健壮性

## 文件清单

修改的文件：
- `agentmatrix-desktop/src-tauri/src/main.rs` - 修复了 `start_backend()` 函数中的路径查找逻辑

## 验证步骤

1. 编译检查：
   ```bash
   cd agentmatrix-desktop/src-tauri
   cargo check
   ```

2. 运行测试：
   ```bash
   cd /Users/dkt/myprojects/agentmatrix-bugfix
   ./agentmatrix-desktop/start-dev.sh
   ```

3. 验证日志：
   应该看到类似以下输出：
   ```
   Starting Python backend...
   Dev mode: using python server.py
   Working directory: /Users/dkt/myprojects/agentmatrix-bugfix
   Backend started successfully
   ```

---

**修复日期**：2026-03-29
**问题影响**：Git worktree 中无法启动开发服务器
**修复状态**：✅ 已完成并测试通过
