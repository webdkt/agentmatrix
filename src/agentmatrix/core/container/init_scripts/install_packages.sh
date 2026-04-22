#!/bin/bash
# 容器内包安装脚本
# 由 Tauri 通过容器 exec 调用
# 支持：延迟加载重型依赖（LibreOffice、Playwright 浏览器、npm 全局包）

set -e

# 打印进度函数
# 格式: PROGRESS:stage:stage_name:percent:message
print_progress() {
    local stage="$1"
    local percent="$2"
    local message="$3"
    echo "PROGRESS:stage:${stage}:${percent}:${message}"
}

# 带重试的安装函数
install_with_retry() {
    local max_attempts=3
    local attempt=1
    local description="$1"
    shift

    while [ $attempt -le $max_attempts ]; do
        if "$@"; then
            return 0
        fi

        if [ $attempt -lt $max_attempts ]; then
            local wait_time=$((5 * attempt))
            echo "PROGRESS:message:${description}失败，${wait_time}秒后重试 ($attempt/$max_attempts)..."
            sleep $wait_time
        fi

        attempt=$((attempt + 1))
    done

    return 1
}

# ═══════════════════════════════════════════════════════════════
# 阶段 1: 核心必需包（必须安装成功）
# ═══════════════════════════════════════════════════════════════

print_progress "core" "0" "开始安装核心组件"

# 更新 apt 缓存
apt-get update -qq
print_progress "core" "10" "已更新 apt 缓存"

# 安装系统依赖（PDF 处理核心）
apt-get install -y --no-install-recommends \
    poppler-utils \
    libpoppler-cpp-dev \
    libxml2 \
    libxslt1.1 \
    > /dev/null 2>&1
print_progress "core" "30" "已安装系统依赖"

# 安装 Python 核心依赖（PDF/文本处理）
pip install --no-cache-dir --quiet \
    PyMuPDF>=1.23.0 \
    pdfplumber>=0.10.0 \
    beautifulsoup4>=4.12.0 \
    html2text>=2020.1.16 \
    trafilatura>=1.6.0 \
    python-pptx>=0.6.21 \
    markitdown[pptx]>=0.1.0
print_progress "core" "100" "核心组件安装完成"

# ═══════════════════════════════════════════════════════════════
# 阶段 2: LibreOffice（可选，失败可跳过）
# ═══════════════════════════════════════════════════════════════

print_progress "libreoffice" "0" "开始安装 LibreOffice"

if install_with_retry "LibreOffice" apt-get install -y --no-install-recommends libreoffice > /dev/null 2>&1; then
    print_progress "libreoffice" "100" "LibreOffice 安装完成"
else
    print_progress "libreoffice" "0" "LibreOffice 安装失败，已跳过"
fi

# ═══════════════════════════════════════════════════════════════
# 阶段 3: Playwright 浏览器（可选，失败可跳过）
# ═══════════════════════════════════════════════════════════════

print_progress "browsers" "0" "开始安装 Playwright 浏览器"

# 确保共享目录存在并设置权限
mkdir -p /opt/ms-playwright
chmod 755 /opt/ms-playwright

# 安装浏览器到共享路径
if install_with_retry "Playwright浏览器" npx playwright install chromium --with-deps > /dev/null 2>&1; then
    # 创建用户设置脚本（为新用户创建符号链接）
    cat > /usr/local/bin/setup-playwright-for-user.sh <<'EOF'
#!/bin/bash
# 为新用户创建 Playwright 浏览器缓存链接
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    mkdir -p "$HOME/.cache"
    ln -s /opt/ms-playwright "$HOME/.cache/ms-playwright"
fi
EOF
    chmod +x /usr/local/bin/setup-playwright-for-user.sh

    print_progress "browsers" "100" "浏览器安装完成"
else
    print_progress "browsers" "0" "浏览器安装失败，已跳过"
fi

# ═══════════════════════════════════════════════════════════════
# 阶段 4: npm 全局包（可选，失败可跳过）
# ═══════════════════════════════════════════════════════════════

print_progress "npm" "0" "开始安装 npm 全局包"

if install_with_retry "npm全局包" npm install -g pptxgenjs playwright react react-dom sharp > /dev/null 2>&1; then
    print_progress "npm" "100" "npm 全局包安装完成"
else
    print_progress "npm" "0" "npm 全局包安装失败，已跳过"
fi

# ═══════════════════════════════════════════════════════════════
# 安装完成
# ═══════════════════════════════════════════════════════════════

print_progress "complete" "100" "所有组件安装完成"

# 清理 apt 缓存
apt-get clean
rm -rf /var/lib/apt/lists/*
