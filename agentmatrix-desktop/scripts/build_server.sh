#!/bin/bash
# 仅构建 Python 后端
# 运行时机：Python 代码修改后
# 运行时间：1-2 分钟

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(dirname "$SCRIPT_DIR")"
RESOURCES_DIR="$DESKTOP_DIR/src-tauri/resources"
PROJECT_ROOT="$(dirname "$DESKTOP_DIR")"

echo "============================================"
echo "  构建 Python 后端"
echo "============================================"
echo ""

# 安装本地包
echo "📦 安装本地 agentmatrix 包..."
cd "$PROJECT_ROOT"
pip install -e . > /dev/null 2>&1 || echo "  (已安装)"
echo "✅ 本地包已安装"
echo ""

# PyInstaller 构建
echo "🐍 PyInstaller 构建 server..."
rm -rf dist-server/server
python -m PyInstaller server.spec --distpath dist-server

echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# 复制到 resources
echo "📋 复制到 resources..."
mkdir -p "$RESOURCES_DIR"
rm -rf "$RESOURCES_DIR/python_dist"
cp -r dist-server/server "$RESOURCES_DIR/python_dist"

if [ ! -f "$RESOURCES_DIR/python_dist/server" ]; then
    echo "❌ Error: Python executable not found!"
    exit 1
fi

chmod +x "$RESOURCES_DIR/python_dist/server"
echo "✅ Python distribution 已复制到 resources"
echo ""

echo "🎉 Python 后端构建完成！"
echo ""
echo "💡 提示:"
echo "  - 如需构建完整 .app，运行: ./scripts/build_app.sh"
echo ""
