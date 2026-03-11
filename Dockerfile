FROM python:3.12-slim

# 安装基础工具
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    git \
    vim \
    tree \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（容器内最小依赖）
COPY requirements-docker.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-docker.txt

# 创建目录结构
# /SKILLS - 只读挂载点（全局技能）
# /home - 读写挂载点（Agent Home）
# /work_files_base - 读写挂载点（所有 session 的工作文件父目录）
RUN mkdir -p /SKILLS /home /work_files_base

# 使用根目录作为默认工作目录，避免符号链接问题
WORKDIR /

# 设置环境变量
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 保持容器运行
CMD ["tail", "-f", "/dev/null"]
