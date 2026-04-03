FROM python:3.12-slim

# 安装基础工具和 Office/PDF 处理依赖
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    git \
    vim \
    tree \
    wget \
    unzip \
    ssh \
    make \
    gcc \
    # Office 文档处理依赖
    libxml2 \
    libxslt1.1 \
    # PDF 处理依赖
    libpoppler-cpp-dev \
    poppler-utils \
    # 图像处理依赖
    libjpeg-dev \
    libpng-dev \
    # 清理缓存
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js 20.x LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（容器内最小依赖）
COPY requirements-docker.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-docker.txt

# 创建目录结构
# /data/agents - 所有 Agent 数据的挂载点（每个 Agent 一个子目录）
RUN mkdir -p /data/agents

# 使用根目录作为默认工作目录，避免符号链接问题
WORKDIR /

# 设置环境变量
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 保持容器运行
CMD ["tail", "-f", "/dev/null"]
