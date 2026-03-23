# Worktree 并行开发指南

## 快速开始

### 首次使用

```bash
chmod +x start_worktree.sh cleanup_worktree.sh
```

### 创建新 worktree

```bash
./start_worktree.sh <功能名称>
```

**示例**：
```bash
# 创建容器运行时功能分支
./start_worktree.sh container-runtime

# 创建 wizard 改进分支
./start_worktree.sh wizard-polish
```

**自动完成**：
- ✅ 创建 worktree：`/Users/dkt/myprojects/agentmatrix-<名称>`
- ✅ 创建分支：`feature/<名称>`
- ✅ 基于最新的 main 分支

### 切换到已存在的 worktree

```bash
./start_worktree.sh <已存在的名称>
```

会显示 worktree 信息和切换命令。

### 列出所有 worktree

```bash
./start_worktree.sh -l
```

### 清理 worktree

```bash
./cleanup_worktree.sh
```

交互式选择要删除的 worktree。

---

## 使用流程

### 场景 1：开始新功能

```bash
# 终端 1：创建 worktree
./start_worktree.sh new-feature

# 切换到 worktree
cd /Users/dkt/myprojects/agentmatrix-new-feature

# 开始开发...
```

### 场景 2：并行开发

```bash
# 终端 1：后端功能
cd /Users/dkt/myprojects/agentmatrix-backend
# ... 开发后端 ...

# 终端 2：前端功能
cd /Users/dkt/myprojects/agentmatrix-frontend
# ... 开发前端 ...

# 完全独立，互不干扰！
```

### 场景 3：完成功能

```bash
# 1. 提交代码
cd /Users/dkt/myprojects/agentmatrix-new-feature
git add .
git commit -m "feat: 新功能"
git push

# 2. 清理 worktree
cd /Users/dkt/myprojects/agentmatrix
./cleanup_worktree.sh
# 选择 new-feature
# 选择是否删除分支
```

---

## 目录结构

```
/Users/dkt/myprojects/
├── agentmatrix/                    # 主仓库 (main)
├── agentmatrix-container-runtime/  # worktree 1
├── agentmatrix-wizard/             # worktree 2
└── agentmatrix-bugfix/             # worktree 3
```

---

## 注意事项

1. **前提条件**：假设远程默认分支名为 `main`
2. **提交后再清理**：确保代码已推送到远程
3. **检查未提交更改**：清理脚本会提醒你
4. **分支管理**：可以选择保留或删除分支（本地删除，远程需手动）
5. **主仓库**：`agentmatrix/` 保持为 main 分支

---

## 常见问题

**Q: worktree 和分支有什么区别？**
A: Worktree 是独立的工作目录，分支是版本历史。一个 worktree 对应一个分支。

**Q: 可以同时在不同 worktree 工作吗？**
A: 可以！这正是 worktree 的用途。

**Q: 删除 worktree 会删除代码吗？**
A: 不会。代码已提交到 Git，worktree 只是工作目录。

**Q: 如何查看所有 worktree？**
A: `./start_worktree.sh -l` 或 `git worktree list`
