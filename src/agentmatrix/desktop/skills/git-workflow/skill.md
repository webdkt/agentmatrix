---
name: git-workflow
description: Git 工作流指南，包括初始化仓库、提交更改、创建分支、合并代码、查看历史、撤销更改等常见操作
license: MIT
---

# Git 工作流指南

## 概述

本技能指导你如何正确使用 Git 进行版本控制，包括初始化仓库、提交更改、创建分支、合并代码等常见操作。适合需要管理代码版本的开发场景。

## 前置条件

- 已安装 Git
- 拥有 terminal 访问权限（通过 `file.bash` action）
- 对 Git 基本概念有初步了解

---

## Action: 初始化 Git 仓库

**使用场景**：当项目需要开始版本控制时

**步骤**：

1. 进入项目目录：
   ```bash
   cd /path/to/project
   ```

2. 执行初始化：
   ```bash
   git init
   ```

3. 添加所有文件到暂存区：
   ```bash
   git add .
   ```

4. 首次提交：
   ```bash
   git commit -m "Initial commit"
   ```

**注意事项**：
- 确保项目目录中不需要跟踪的文件已添加到 `.gitignore`
- 提交信息应清晰描述本次提交的内容

---

## Action: 创建新分支

**使用场景**：当需要开发新功能或修复 bug 时，应该创建独立的分支

**步骤**：

1. 确保当前分支干净（无未提交的更改）：
   ```bash
   git status
   ```

2. 如果有未提交的更改，先提交：
   ```bash
   git add .
   git commit -m "Save work before branching"
   ```

3. 创建并切换到新分支：
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. 验证当前分支：
   ```bash
   git branch
   ```

**分支命名规范**：
- 新功能：`feature/功能名称`
- Bug 修复：`bugfix/问题描述`
- 紧急修复：`hotfix/问题描述`

**注意事项**：
- 从 `main` 或 `develop` 分支创建新分支
- 分支名称应使用小写字母和连字符

---

## Action: 提交更改

**使用场景**：当完成一部分工作，需要保存进度时

**步骤**：

1. 查看修改状态：
   ```bash
   git status
   ```

2. 查看具体修改内容：
   ```bash
   git diff
   ```

3. 添加文件到暂存区：
   ```bash
   # 添加特定文件
   git add path/to/file

   # 添加所有文件
   git add .
   ```

4. 提交更改：
   ```bash
   git commit -m "描述性提交信息"
   ```

**提交信息规范**：
- 使用清晰的、描述性的语言
- 第一行简短总结（50 字符以内）
- 如需详细说明，空一行后添加具体描述

**示例**：
```
Add user authentication feature

- Implement login form validation
- Add JWT token handling
- Create user session management
```

---

## Action: 合并分支

**使用场景**：当功能开发完成，需要将代码合并回主分支时

**步骤**：

1. 切换到目标分支（如 main）：
   ```bash
   git checkout main
   ```

2. 确保目标分支是最新的：
   ```bash
   git pull origin main
   ```

3. 合并源分支：
   ```bash
   git merge feature/your-feature
   ```

4. 如果有冲突，解决冲突后：
   ```bash
   git add .
   git commit
   ```

5. 删除已合并的分支（可选）：
   ```bash
   git branch -d feature/your-feature
   ```

**注意事项**：
- 合并前确保目标分支是最新的
- 如果出现冲突，需要手动解决冲突文件
- 使用 `git log` 查看合并历史

---

## Action: 查看历史记录

**使用场景**：需要查看项目历史或追踪某个更改时

**步骤**：

1. 查看提交历史：
   ```bash
   git log
   ```

2. 查看简洁的历史（一行显示）：
   ```bash
   git log --oneline
   ```

3. 查看图形化历史：
   ```bash
   git log --graph --oneline --all
   ```

4. 查看特定文件的修改历史：
   ```bash
   git log path/to/file
   ```

5. 查看某次提交的详细更改：
   ```bash
   git show <commit-hash>
   ```

**注意事项**：
- 使用 `q` 键退出 log 查看界面
- commit-hash 可以使用前几位（通常 7 位即可）

---

## Action: 撤销更改

**使用场景**：当需要撤销某些更改时

### 场景 1：撤销工作区的更改（未 add）

```bash
# 恢复单个文件
git restore path/to/file

# 恢复所有文件
git restore .
```

### 场景 2：撤销暂存区的更改（已 add，未 commit）

```bash
# 取消暂存
git reset

# 恢复到工作区
git restore path/to/file
```

### 场景 3：撤销提交（已 commit）

```bash
# 撤销最后一次提交，保留更改
git reset --soft HEAD~1

# 撤销最后一次提交，丢弃更改
git reset --hard HEAD~1

# 撤销指定提交
git revert <commit-hash>
```

**注意事项**：
- `--hard` 操作会永久删除更改，谨慎使用
- `revert` 会创建新的提交来撤销之前的提交

---

## 常见问题

### Q: 如何查看当前分支？

A: 使用 `git branch` 命令，当前分支前会有 `*` 标记。

### Q: 如何查看远程仓库？

A: 使用 `git remote -v` 查看配置的远程仓库。

### Q: 如何推送代码到远程？

A: 使用 `git push origin <branch-name>` 推送当前分支。

### Q: 如何拉取远程更新？

A: 使用 `git pull origin <branch-name>` 拉取并合并远程更新。

---

## 最佳实践

1. **频繁提交**：小步快跑，频繁提交可以更好地追踪历史
2. **清晰的提交信息**：让他人（和未来的自己）容易理解每个提交的目的
3. **使用分支**：不要直接在 main 分支上开发
4. **代码审查**：合并前进行代码审查，确保质量
5. **保持主分支稳定**：main 分支应始终保持可发布状态

---

## 相关资源

- Git 官方文档：https://git-scm.com/doc
- GitHub 指南：https://guides.github.com/
- Git 交互式学习：https://learngitbranching.js.org/
