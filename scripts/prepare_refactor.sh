#!/bin/bash
# 准备开始 Skill 重构
# 创建安全点和功能分支

set -e

echo "======================================"
echo "Skill 重构准备脚本"
echo "======================================"
echo ""

# 1. 检查当前状态
echo "1️⃣ 检查当前状态..."
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ 当前有未提交的更改，请先提交或暂存"
    git status
    exit 1
fi
echo "✅ 工作区干净"
echo ""

# 2. 运行所有测试
echo "2️⃣ 运行所有测试..."
pytest tests/ -v
if [ $? -ne 0 ]; then
    echo "❌ 测试失败，请先修复测试"
    exit 1
fi
echo "✅ 所有测试通过"
echo ""

# 3. 创建功能分支
echo "3️⃣ 创建功能分支..."
BRANCH_NAME="feature/skill-refactor"
if git rev-parse --verify $BRANCH_NAME >/dev/null 2>&1; then
    echo "⚠️  分支 $BRANCH_NAME 已存在"
    read -p "是否删除并重新创建？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git branch -D $BRANCH_NAME
        git checkout -b $BRANCH_NAME
    else
        git checkout $BRANCH_NAME
    fi
else
    git checkout -b $BRANCH_NAME
fi
echo "✅ 当前分支: $BRANCH_NAME"
echo ""

# 4. 创建安全点
echo "4️⃣ 创建安全点..."
SAFE_POINT_COMMIT=$(git rev-parse HEAD)
echo $SAFE_POINT_COMMIT > .safe_point
echo "✅ Safe point: $SAFE_POINT_COMMIT"
echo ""

# 5. 创建 pre-refactor tag
echo "5️⃣ 创建 pre-refactor tag..."
git tag pre-skill-refactor -f
echo "✅ Tag: pre-skill-refactor"
echo ""

# 6. 创建初始 commit
echo "6️⃣ 创建初始 commit..."
git commit --allow-empty -m "refactor: start skill refactoring - safe point

Safe point before starting skill refactoring work.
Rollback: git reset --hard $SAFE_POINT_COMMIT
"
echo "✅ 初始 commit 已创建"
echo ""

# 7. 总结
echo "======================================"
echo "✅ 准备完成！"
echo "======================================"
echo ""
echo "当前状态："
echo "  分支: $BRANCH_NAME"
echo "  Safe point: $SAFE_POINT_COMMIT"
echo "  Tag: pre-skill-refactor"
echo ""
echo "下一步："
echo "  1. 阅读 docs/architecture/skill-refactoring-plan.md"
echo "  2. 开始 Phase 1: 为所有 skill 添加元数据"
echo ""
echo "回滚命令："
echo "  git reset --hard $SAFE_POINT_COMMIT"
echo "  git checkout main"
echo ""
