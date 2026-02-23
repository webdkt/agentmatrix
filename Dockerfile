FROM python:3.12-slim

# 安装基础工具
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（容器内最小依赖）
COPY requirements-docker.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 创建目录结构
RUN mkdir -p /skills /home /workspace

WORKDIR /workspace

# 保持容器运行
CMD ["tail", "-f", "/dev/null"]
