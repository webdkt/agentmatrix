#!/bin/bash
# AgentMatrix 完整构建脚本（已迁移）
#
# ⚠️  注意：构建脚本已迁移到 scripts/ 目录
#
# 新的构建流程：
#   1. 首次构建: ./scripts/setup_cache.sh && ./scripts/build_all.sh
#   2. 日常构建: ./scripts/build_all.sh
#
# 详细说明: ./scripts/README.md
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  AgentMatrix 构建脚本已迁移"
echo "============================================"
echo ""
echo "⚠️  注意：构建脚本已迁移到 scripts/ 目录"
echo ""
echo "新的使用方式："
echo ""
echo "  📖 查看文档:"
echo "     cat scripts/README.md"
echo ""
echo "  🔨 首次构建（准备缓存）:"
echo "     ./scripts/setup_cache.sh"
echo ""
echo "  🏗️  完整构建（使用缓存）:"
echo "     ./scripts/build_all.sh"
echo ""
echo "  🐍 仅构建 Python 后端:"
echo "     ./scripts/build_server.sh"
echo ""
echo "  📱 仅构建 Tauri App:"
echo "     ./scripts/build_app.sh"
echo ""
echo "自动跳转到新的构建脚本..."
echo ""

# 自动跳转
exec "$SCRIPT_DIR/scripts/build_all.sh" "$@"
