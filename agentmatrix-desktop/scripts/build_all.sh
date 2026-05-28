#!/bin/bash
# 完整构建（PyInstaller + Tauri）
# 运行时机：日常开发、发版

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(dirname "$SCRIPT_DIR")"
RESOURCES_DIR="$DESKTOP_DIR/src-tauri/resources"
PROJECT_ROOT="$(dirname "$DESKTOP_DIR")"

echo "============================================"
echo "  AgentMatrix 构建"
echo "============================================"
echo ""

# ========================================
# 步骤 1: 安装本地包
# ========================================
echo "📦 步骤 1/3: 安装本地 agentmatrix 包..."
cd "$PROJECT_ROOT"
pip install -e . > /dev/null 2>&1 || echo "  (已安装)"
echo "✅ 本地包已安装"
echo ""

# ========================================
# 步骤 2: PyInstaller 构建
# ========================================
echo "🐍 步骤 2/3: PyInstaller 构建 server..."
cd "$PROJECT_ROOT"
rm -rf dist-server/server
python -m PyInstaller server.spec --distpath dist-server
echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# ========================================
# 步骤 3: 复制 Python distribution
# ========================================
echo "📋 步骤 3/3: 复制 Python distribution..."
mkdir -p "$RESOURCES_DIR"
rm -rf "$RESOURCES_DIR/python_dist"
echo "  → 复制 dist-server/server → resources/python_dist"
cp -r dist-server/server "$RESOURCES_DIR/python_dist"

if [ ! -f "$RESOURCES_DIR/python_dist/server" ]; then
    echo "❌ Error: Python executable not found!"
    exit 1
fi

chmod +x "$RESOURCES_DIR/python_dist/server"
echo "✅ Python distribution 已复制"
echo ""

# ========================================
# Tauri 构建
# ========================================
echo "🏗️  Tauri 构建..."
cd "$DESKTOP_DIR"
npm run tauri:build
echo ""

echo "============================================"
echo "✅ 构建完成！"
echo "============================================"
echo ""

BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
if [ -d "$BUNDLE_DIR/macos" ]; then
    echo "📦 macOS 安装包:"
    ls -lh "$BUNDLE_DIR/macos/"*.dmg 2>/dev/null | awk '{print "  " $9 ": " $5}'
fi
echo ""
echo "🎉 所有步骤完成！"
