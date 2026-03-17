#!/bin/bash

# AgentMatrix 开发环境设置脚本

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 Setting up AgentMatrix development environment..."

# 设置 PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"

echo "✅ PYTHONPATH set to: $PROJECT_DIR/src"
echo ""
echo "📝 Development environment ready!"
echo "   - AgentMatrix package: src/agentmatrix/"
echo "   - Server script: server.py"
echo ""
echo "💡 Usage:"
echo "   python server.py --matrix-world examples/MyWorld"
echo ""

# 执行传入的命令
if [ $# -gt 0 ]; then
  exec "$@"
fi
