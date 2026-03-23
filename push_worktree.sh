#!/bin/bash
# push_worktree.sh - 在 worktree 中执行，推送当前分支到远程
# 用法: 在 worktree 目录下运行 ./push_worktree.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# 检查是否在 git 仓库中
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_error "当前目录不在 git 仓库中"
    exit 1
fi

BRANCH=$(git branch --show-current)
log_info "当前分支: $BRANCH"

# 检查未提交的更改
if [ -n "$(git status --porcelain)" ]; then
    log_warning "有未提交的更改:"
    git status --short
    echo ""
    read -p "是否先提交这些更改? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "提交信息: " commit_msg
        if [ -z "$commit_msg" ]; then
            log_error "提交信息不能为空"
            exit 1
        fi
        git add -A
        git commit -m "$commit_msg"
        log_success "已提交"
    else
        log_warning "跳过提交，只推送已有的提交"
    fi
fi

# 检查是否有提交可推送
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "")

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    log_success "已经是最新，无需推送"
    exit 0
fi

# 推送
log_info "推送到 origin/$BRANCH ..."
if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    git push
else
    git push -u origin "$BRANCH"
fi

log_success "推送完成!"
echo ""
echo "下一步: 回到主仓库目录，运行 cleanup_worktree.sh 合并并清理"
echo "  cd /Users/dkt/myprojects/agentmatrix"
echo "  ./cleanup_worktree.sh"
