# Working Directory 未设置问题修复

## 🐛 问题描述

运行 `start-dev.sh` 时出现以下错误：

```
Dev mode: using python server.py
Backend started successfully
python: can't open file '/Users/dkt/myprojects/agentmatrix-bugfix/agentmatrix-desktop/src-tauri/server.py': [Errno 2] No such file or directory
```

**关键信息**：
- python 在 `src-tauri` 目录下查找 `server.py`
- 但 `server.py` 实际在项目根目录
- 说明 working directory 没有被正确设置

## 🔍 根本原因

### 问题分析

原始代码结构：
```rust
if !server_args.is_empty() {
    if let Some(resource_dir) = app.path().resource_dir().ok() {
        // 设置 working directory
    }
}
```

**问题**：
1. **嵌套条件**：有两层 if 条件
2. **Dev 模式下 `resource_dir()` 不可用**：
   - Dev 模式没有打包资源文件
   - `app.path().resource_dir()` 可能返回 `None` 或错误
   - 导致整个代码块被跳过

### 结果

```
Dev 模式启动流程：
1. get_server_path() → ("python", ["server.py"])  ✅
2. server_args.is_empty() → false  ✅
3. resource_dir().ok() → None  ❌ (Dev 模式下不可用)
4. 整个代码块被跳过  ❌
5. working directory 没有被设置  ❌
6. python 在 src-tauri 目录下启动  ❌
7. 找不到 server.py  💥
```

## ✅ 解决方案

### 修复思路

**移除嵌套条件**，将 dev 模式的逻辑独立出来：
```rust
if !server_args.is_empty() {
    let project_root = if cfg!(dev) {
        // Dev 模式：不依赖 resource_dir
        // 直接使用 CARGO_MANIFEST_DIR
        ...
    } else {
        // Production 模式：使用 resource_dir
        if let Some(resource_dir) = app.path().resource_dir().ok() {
            ...
        }
    };
    cmd.current_dir(&project_root);
}
```

### 修改前后对比

**修改前**（有问题的代码）：
```rust
if !server_args.is_empty() {
    // ❌ 嵌套条件：dev 模式下 resource_dir 不可用
    if let Some(resource_dir) = app.path().resource_dir().ok() {
        let project_root = if cfg!(dev) {
            // Dev 模式逻辑
            ...
        } else {
            // Production 模式逻辑
            ...
        };
        cmd.current_dir(&project_root);
    }
    // ❌ 如果 resource_dir 不可用，working directory 就不会被设置
}
```

**修改后**（修复的代码）：
```rust
if !server_args.is_empty() {
    // ✅ 外层条件：根据模式选择不同的逻辑
    let project_root = if cfg!(dev) {
        // Dev 模式：使用 CARGO_MANIFEST_DIR（编译时常量）
        let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let project_root = manifest_dir.parent()
            .and_then(|p| p.parent())
            .unwrap_or(&manifest_dir);

        // 验证 server.py 存在
        if !project_root.join("server.py").exists() {
            // Fallback 逻辑
            ...
        } else {
            project_root.to_path_buf()
        }
    } else {
        // Production 模式：使用 resource_dir
        if let Some(resource_dir) = app.path().resource_dir().ok() {
            resource_dir.parent()
                .and_then(|p| p.parent())
                .map(|p| p.to_path_buf())
                .unwrap_or_else(|| resource_dir.clone())
        } else {
            // Fallback
            std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."))
        }
    };

    // ✅ 总是设置 working directory
    cmd.current_dir(&project_root);
    println!("Working directory: {:?}", project_root);
}
```

## 🎯 关键改进

### 1. Dev 模式独立逻辑
```rust
if cfg!(dev) {
    // ✅ 不依赖 resource_dir
    // ✅ 使用编译时常量 CARGO_MANIFEST_DIR
    // ✅ 总是能找到项目根目录
}
```

### 2. 移除嵌套条件
```rust
// 修改前：if !server_args.is_empty() { if let Some(resource_dir) = ... { ... } }
// 修改后：if !server_args.is_empty() { let project_root = if cfg!(dev) { ... } }
```

### 3. 更好的错误处理
```rust
if !project_root.join("server.py").exists() {
    eprintln!("Warning: server.py not found at {:?}", project_root.join("server.py"));
    // Fallback 搜索逻辑
}
```

## 📊 验证结果

### 路径解析测试

```bash
CARGO_MANIFEST_DIR: /Users/dkt/myprojects/agentmatrix-bugfix/agentmatrix-desktop/src-tauri
Project root (2 levels up): /Users/dkt/myprojects/agentmatrix-bugfix
server.py path: /Users/dkt/myprojects/agentmatrix-bugfix/server.py
✅ server.py 存在！
✅ Working directory 应该设置为: /Users/dkt/myprojects/agentmatrix-bugfix
```

### 预期日志输出

```
Starting Python backend...
Using MatrixWorld path: "/Users/dkt/myprojects/agentmatrix/examples/MyWorld"
Dev mode: using python server.py
Working directory: "/Users/dkt/myprojects/agentmatrix-bugfix"  ✅
Backend started successfully  ✅
```

## 🔄 与之前修复的关系

### 第一次修复（Git Worktree 兼容性）
- **问题**：符号链接导致路径查找跳到错误的仓库
- **解决**：使用 `CARGO_MANIFEST_DIR` 而不是从 `resource_dir` 搜索

### 第二次修复（本修复）
- **问题**：Dev 模式下 `resource_dir()` 不可用，导致 working directory 未设置
- **解决**：移除嵌套条件，确保 dev 模式总是设置 working directory

### 两者的关系

```
第一次修复：
├─ 使用 CARGO_MANIFEST_DIR ✅
└─ 但代码结构有问题（嵌套条件）❌

第二次修复：
├─ 保持使用 CARGO_MANIFEST_DIR ✅
├─ 修复代码结构（移除嵌套条件）✅
└─ 确保总是设置 working directory ✅
```

## 📝 修改总结

### 修改的文件
- `agentmatrix-desktop/src-tauri/src/main.rs`

### 修改的内容
- 重构了 working directory 设置逻辑
- 移除了 `resource_dir` 的嵌套条件
- 确保在 dev 模式下总是能设置 working directory

### 代码行数
- 修改：约 40 行
- 重构：条件逻辑优化

## ✅ 修复完成

**修复日期**：2026-03-29
**影响范围**：Dev 模式启动（`cargo run`）
**Production 影响**：无
**修复状态**：✅ 已完成并编译通过

## 🧪 测试步骤

1. **重新编译**：
   ```bash
   cd agentmatrix-desktop/src-tauri
   cargo build
   ```

2. **启动开发服务器**：
   ```bash
   cd /Users/dkt/myprojects/agentmatrix-bugfix
   ./agentmatrix-desktop/start-dev.sh
   ```

3. **验证日志**：
   应该看到：
   ```
   Dev mode: using python server.py
   Working directory: "/Users/dkt/myprojects/agentmatrix-bugfix"
   Backend started successfully
   ```

4. **不应该再看到**：
   ```
   python: can't open file '.../src-tauri/server.py'
   ```

---

**预期效果**：
- ✅ Dev 模式能正确找到 server.py
- ✅ Working directory 被正确设置为项目根目录
- ✅ Git worktree 兼容性保持
- ✅ Production 构建不受影响
