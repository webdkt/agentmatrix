#!/bin/bash
# 统计 Tauri V2 + Vue + Python 项目代码行数

# 通用排除项
EXCLUDE="(node_modules|\.git|target|dist|venv|\.venv|__pycache__|\.pytest_cache|\.mypy_cache|gen/schemas|public/fonts|resources/icons|meridian-demo)"

echo "========================================"
echo "        项目代码行数统计"
echo "========================================"
echo ""

# 1. Python（后端核心）
echo "🐍 Python 后端"
py_lines=$(find . -type f \( -name "*.py" \) \
  ! -path "*/$EXCLUDE/*" \
  ! -name "*.pyc" \
  ! -name "test_pyinstaller_skills.py" \
  | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "   行数: ${py_lines:-0}"
echo ""

# 2. Vue / JS / CSS / HTML（前端）
echo "🎨 Vue 前端 (JS/Vue/CSS/HTML)"
fe_lines=$(find ./agentmatrix-desktop/src -type f \( \
  -name "*.vue" -o -name "*.js" -o -name "*.ts" -o -name "*.css" -o -name "*.html" -o -name "*.jsx" -o -name "*.tsx" \
  \) 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "   agentmatrix-desktop/src 行数: ${fe_lines:-0}"
echo ""

# 3. Rust（Tauri）
echo "⚙️  Tauri Rust"
rs_lines=$(find ./agentmatrix-desktop/src-tauri/src -type f -name "*.rs" 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "   src-tauri/src 行数: ${rs_lines:-0}"
echo ""

# 4. Shell / 脚本
echo "📜 Shell 脚本"
sh_lines=$(find . -type f \( -name "*.sh" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/target/*" ! -path "*/__pycache__/*" \
  | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "   行数: ${sh_lines:-0}"
echo ""

# 5. 配置文件（YML/JSON/TOML等）
echo "⚙️  配置文件 (YML/YAML/JSON/TOML/conf)"
cfg_lines=$(find . -type f \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.toml" -o -name "*.conf" -o -name "*.cfg" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/target/*" ! -path "*/__pycache__/*" \
  ! -name "package-lock.json" ! -name "Cargo.lock" \
  | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "   行数: ${cfg_lines:-0}"
echo ""

# 6. Markdown / 文档
echo "📝 Markdown 文档"
md_lines=$(find . -type f -name "*.md" \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/target/*" ! -path "*/__pycache__/*" \
  | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "   行数: ${md_lines:-0}"
echo ""

# 汇总（核心代码）
total=$(( ${py_lines:-0} + ${fe_lines:-0} + ${rs_lines:-0} ))
echo "========================================"
echo "        核心代码汇总（不含文档/配置）"
echo "========================================"
echo "  Python:      ${py_lines:-0} 行"
echo "  Vue/前端:    ${fe_lines:-0} 行"
echo "  Rust/Tauri:  ${rs_lines:-0} 行"
echo "  ─────────────────────────────"
echo "  核心合计:    $total 行"
echo "========================================"
