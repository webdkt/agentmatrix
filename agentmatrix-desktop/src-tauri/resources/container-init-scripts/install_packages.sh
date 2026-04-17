#!/bin/bash
# 容器内包安装脚本
# 由 Tauri 通过容器 exec 调用
# 支持：延迟加载重型依赖（LibreOffice、Playwright 浏览器、npm 全局包）

set -e

# ═══════════════════════════════════════════════════════════════
# 智能镜像源选择（自动检测网络环境，选择最快的镜像）
# ═══════════════════════════════════════════════════════════════

# 检测网络环境函数：通过测试延迟判断是否在国内
detect_network_region() {
    # 测试访问国内镜像的延迟（清华源）
    local cn_latency=$(timeout 2 curl -o /dev/null -s -w '%{time_total}\n' https://mirrors.tuna.tsinghua.edu.cn 2>/dev/null || echo "999")

    # 测试访问官方源的延迟
    local global_latency=$(timeout 2 curl -o /dev/null -s -w '%{time_total}\n' https://deb.debian.org 2>/dev/null || echo "999")

    echo "🔍 网络延迟检测 - 清华源: ${cn_latency}s, 官方源: ${global_latency}s"

    # 如果国内源延迟小于 1 秒，或者明显快于官方源，则判断为国内网络
    if (( $(echo "$cn_latency < 1.0" | bc -l) )) || (( $(echo "$cn_latency < $global_latency" | bc -l) )); then
        echo "china"
    else
        echo "global"
    fi
}

# 检测网络环境
REGION=$(detect_network_region)
echo "PROGRESS:stage:detect:0:检测到网络环境: $REGION"

# 根据网络环境配置镜像源
if [ "$REGION" = "china" ]; then
    # 国内镜像源配置
    echo "PROGRESS:stage:detect:50:使用国内镜像源（清华源/npmmirror）"

    # APT 镜像（清华源）
    if ! grep -q "mirrors.tuna.tsinghua.edu.cn" /etc/apt/sources.list.d/debian.sources 2>/dev/null; then
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true
    fi

    # pip 镜像（清华源）
    export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null || true

    # npm 镜像（npmmirror）
    npm config set registry https://registry.npmmirror.com

    # Playwright 镜像
    export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
else
    # 国际镜像源配置（使用官方源）
    echo "🌐 使用国际官方源"

    # 确保使用官方 APT 源
    if grep -q "mirrors.tuna.tsinghua.edu.cn" /etc/apt/sources.list.d/debian.sources 2>/dev/null; then
        sed -i 's/mirrors.tuna.tsinghua.edu.cn/deb.debian.org/g' /etc/apt/sources.list.d/debian.sources
    fi

    # pip 使用官方源（清除配置）
    pip config unset global.index-url 2>/dev/null || true
    unset PIP_INDEX_URL

    # npm 使用官方源
    npm config set registry https://registry.npmjs.org

    # Playwright 使用官方源
    unset PLAYWRIGHT_DOWNLOAD_HOST
fi

echo "PROGRESS:stage:detect:100:镜像源配置完成"

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
    libxslt1.1
print_progress "core" "30" "已安装系统依赖"

# 安装 Python 核心依赖（PDF/文本处理）
pip install --no-cache-dir \
    PyMuPDF>=1.23.0 \
    pdfplumber>=0.10.0 \
    beautifulsoup4>=4.12.0 \
    html2text>=2020.1.16 \
    trafilatura>=1.6.0
print_progress "core" "100" "核心组件安装完成"

# ═══════════════════════════════════════════════════════════════
# 阶段 2: LibreOffice（可选，失败可跳过）
# ═══════════════════════════════════════════════════════════════

print_progress "libreoffice" "0" "开始安装 LibreOffice"

if install_with_retry "LibreOffice" apt-get install -y --no-install-recommends libreoffice; then
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
if install_with_retry "Playwright浏览器" npx playwright install chromium --with-deps; then
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

if install_with_retry "npm全局包" npm install -g pptxgenjs playwright react react-dom sharp; then
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
