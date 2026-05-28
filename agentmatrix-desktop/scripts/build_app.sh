#!/bin/bash
# 仅构建 Tauri App
# 运行时机：前端代码修改后
# 前提：Python 后端已准备好
# 运行时间：1-2 分钟

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(dirname "$SCRIPT_DIR")"
RESOURCES_DIR="$DESKTOP_DIR/src-tauri/resources"

echo "============================================"
echo "  构建 Tauri App"
echo "============================================"
echo ""

# 检查必要的资源
echo "🔍 检查必要资源..."
if [ ! -f "$RESOURCES_DIR/python_dist/server" ]; then
    echo "❌ Python backend 未找到: $RESOURCES_DIR/python_dist/server"
    echo ""
    echo "请先运行: ./scripts/build_all.sh"
    exit 1
fi

echo "✅ Python backend 已就绪"
ls -lh "$RESOURCES_DIR/python_dist/server" | awk '{print "  Python:  " $9 ": " $5}'
echo ""

# Tauri 构建
echo "🏗️  开始 Tauri 构建..."
cd "$DESKTOP_DIR"
npm run tauri:build
echo ""

# 总结
echo "============================================"
echo "✅ App 构建完成！"
echo "============================================"
echo ""

BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
if [ -d "$BUNDLE_DIR/macos" ]; then
    DMG_PATH=$(ls "$BUNDLE_DIR/macos/"*.dmg 2>/dev/null | head -1)
    if [ -n "$DMG_PATH" ]; then
        echo "📦 安装包: $DMG_PATH"
        ls -lh "$DMG_PATH" | awk '{print "   大小: " $5}'
    fi
fi
echo ""
echo "🎉 Tauri App 构建完成！"
