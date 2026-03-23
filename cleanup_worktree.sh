#!/bin/bash
# cleanup_worktree.sh - 清理 worktree 脚本

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

# 读取 worktree 列表（兼容 bash 3.2）
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
        log_warning "有 $uncommitted_count 个未提交的更改!"
        git status --short | head -5
        if [ "$uncommitted_count" -gt 5 ]; then
            echo "  ... 还有 $((uncommitted_count - 5)) 个文件"
        fi
        echo ""
        read -p "仍然继续? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "取消操作"
            exit 0
        fi
    fi
fi

# 询问是否删除分支
echo ""
read -p "删除分支 '$branch_name'? (y/n) " -n 1 -r
echo
delete_branch=false
if [[ $REPLY =~ ^[Yy]$ ]]; then
    delete_branch=true
fi

# 确认
echo ""
read -p "确认删除 '$worktree_name'? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "取消操作"
    exit 0
fi

# 删除
cd "$BASE_DIR/$MAIN_REPO"

log_info "删除 worktree..."
git worktree remove "$worktree_path" 2>/dev/null || {
    rm -rf "$worktree_path"
    git worktree prune
}

if [ "$delete_branch" = true ]; then
    git branch -D "$branch_name" 2>/dev/null || true
    echo "提示: 如已推送远程，需手动删除: git push origin --delete $branch_name"
fi

log_success "清理完成!"
