#!/bin/bash
# cleanup_worktree.sh - 在主仓库目录执行，合并分支并清理 worktree
# 用法: cd /Users/dkt/myprojects/agentmatrix && ./cleanup_worktree.sh

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
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

cd "$BASE_DIR/$MAIN_REPO"

# 获取所有 worktree（排除主仓库）
main_repo_path=$(git rev-parse --show-toplevel)

log_info "当前 worktree:"
echo ""

# 创建临时文件存储 worktree 列表
temp_file=$(mktemp)
git worktree list | grep -v "bare$" | while read -r worktree_path branch_info; do
    if [ "$worktree_path" != "$main_repo_path" ]; then
        worktree_name=$(basename "$worktree_path" | sed "s/^agentmatrix-//")
        branch=$(cd "$worktree_path" 2>/dev/null && git branch --show-current 2>/dev/null || echo "unknown")
        echo "$worktree_name|$worktree_path|$branch" >> "$temp_file"
    fi
done

# 读取 worktree 列表
lines=()
while IFS= read -r line; do
    [ -n "$line" ] && lines+=("$line")
done < "$temp_file"
rm -f "$temp_file"

if [ ${#lines[@]} -eq 0 ]; then
    log_info "没有额外的 worktree 可以清理"
    exit 0
fi

# 显示列表
for i in "${!lines[@]}"; do
    IFS='|' read -r name path branch <<< "${lines[$i]}"
    echo "  [$((i+1))] $name ($branch)"
done
echo "  [0] 取消"
echo ""

# 选择
read -p "请输入选项 (0-${#lines[@]}): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 0 ] || [ "$choice" -gt ${#lines[@]} ]; then
    log_error "无效的选择"
    exit 1
fi

if [ "$choice" -eq 0 ]; then
    log_info "取消操作"
    exit 0
fi

selected_index=$((choice - 1))
IFS='|' read -r worktree_name worktree_path branch_name <<< "${lines[$selected_index]}"

# 检查未提交的更改
if [ -d "$worktree_path" ]; then
    cd "$worktree_path"
    uncommitted_count=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

    if [ "$uncommitted_count" -gt 0 ]; then
        log_warning "worktree 中有 $uncommitted_count 个未提交的更改!"
        git status --short | head -5
        if [ "$uncommitted_count" -gt 5 ]; then
            echo "  ... 还有 $((uncommitted_count - 5)) 个文件"
        fi
        echo ""
        read -p "是否先提交? (y/n) " -n 1 -r
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
            # 推送
            git push 2>/dev/null || git push -u origin "$branch_name"
            log_success "已推送"
        else
            log_warning "跳过未提交的更改"
        fi
    fi
fi

# 回到主仓库
cd "$BASE_DIR/$MAIN_REPO"

# ===== 合并到 main =====
log_info "开始合并 $branch_name 到 main ..."

# 确保在 main 分支
git checkout main
git pull origin main

# 检查远程分支是否存在（如果之前没 push 过）
if git rev-parse --verify "origin/$branch_name" >/dev/null 2>&1; then
    git merge "origin/$branch_name" --no-edit
else
    # 本地分支直接合并
    git merge "$branch_name" --no-edit
fi

log_success "合并完成"

# 推送 main
log_info "推送到 origin/main ..."
git push origin main
log_success "推送完成"

# ===== 清理 =====
echo ""
log_info "开始清理..."

# 删除 worktree
log_info "删除 worktree: $worktree_path"
git worktree remove "$worktree_path" 2>/dev/null || {
    rm -rf "$worktree_path"
    git worktree prune
}

# 删除本地分支
log_info "删除本地分支: $branch_name"
git branch -D "$branch_name" 2>/dev/null || true

# 删除远程分支
if git rev-parse --verify "origin/$branch_name" >/dev/null 2>&1; then
    echo ""
    read -p "删除远程分支 origin/$branch_name? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin --delete "$branch_name"
        log_success "远程分支已删除"
    fi
fi

echo ""
log_success "全部完成! 🎉"
echo ""
echo "  worktree: 已删除"
echo "  本地分支: 已删除"
echo "  main: 已合并并推送"
