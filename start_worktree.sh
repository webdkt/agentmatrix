#!/bin/bash
# start_worktree.sh - 简单的 worktree 管理脚本

set -e

BASE_DIR="/Users/dkt/myprojects"
MAIN_REPO="agentmatrix"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# 列出所有 worktree
if [ "$1" = "-l" ] || [ "$1" = "--list" ]; then
    cd "$BASE_DIR/$MAIN_REPO"
    echo "所有 worktree:"
    git worktree list
    exit 0
fi

# 参数检查
if [ -z "$1" ]; then
    echo "用法: ./start_worktree.sh <worktree-name>"
    echo "示例: ./start_worktree.sh container-runtime"
    echo ""
    echo "选项:"
    echo "  -l, --list  列出所有 worktree"
    exit 1
fi

WORKTREE_NAME=$1
WORKTREE_PATH="$BASE_DIR/agentmatrix-$WORKTREE_NAME"
BRANCH_NAME="feature/$WORKTREE_NAME"

# 检查主仓库
if [ ! -d "$BASE_DIR/$MAIN_REPO/.git" ]; then
    log_error "主仓库不存在: $BASE_DIR/$MAIN_REPO"
    exit 1
fi

# Worktree 已存在
if [ -d "$WORKTREE_PATH" ]; then
    log_success "Worktree 已存在: $WORKTREE_NAME"
    cd "$WORKTREE_PATH"
    echo "  路径: $WORKTREE_PATH"
    echo "  分支: $(git branch --show-current)"
    echo ""
    echo "切换命令:"
    echo "  cd $WORKTREE_PATH"
    exit 0
fi

# 创建新 worktree
log_info "创建新 worktree: $WORKTREE_NAME"
cd "$BASE_DIR/$MAIN_REPO"

# 同步远程
git fetch origin main >/dev/null 2>&1

# 创建 worktree 和分支
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" origin/main

# Symlink shared directories (node_modules, Cargo target, etc.)
MAIN_DESKTOP="$BASE_DIR/$MAIN_REPO/agentmatrix-desktop"
WORKTREE_DESKTOP="$WORKTREE_PATH/agentmatrix-desktop"

if [ -d "$MAIN_DESKTOP/node_modules" ] && [ ! -e "$WORKTREE_DESKTOP/node_modules" ]; then
    ln -s "$MAIN_DESKTOP/node_modules" "$WORKTREE_DESKTOP/node_modules"
    log_success "Symlinked node_modules → main repo"
fi

if [ -d "$MAIN_DESKTOP/src-tauri/target" ] && [ ! -e "$WORKTREE_DESKTOP/src-tauri/target" ]; then
    ln -s "$MAIN_DESKTOP/src-tauri/target" "$WORKTREE_DESKTOP/src-tauri/target"
    log_success "Symlinked src-tauri/target → main repo"
fi

log_success "Worktree 创建成功!"
echo "  路径: $WORKTREE_PATH"
echo "  分支: $BRANCH_NAME"
echo ""
echo "开始开发:"
echo "  cd $WORKTREE_PATH"
