#!/bin/bash
# AgentMatrix 容器镜像构建脚本
# 支持 Docker 和 Podman

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认配置
IMAGE_NAME="agentmatrix"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
RUNTIME="auto"  # auto, docker, podman

# 打印帮助信息
usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -r, --runtime RUNTIME    指定容器运行时 (docker|podman|auto)"
    echo "  -n, --name NAME          镜像名称 (默认: agentmatrix)"
    echo "  -t, --tag TAG           镜像标签 (默认: latest)"
    echo "  -h, --help              显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                      # 使用默认配置构建"
    echo "  $0 -r docker            # 使用 Docker 构建"
    echo "  $0 -r podman -t v1.0    # 使用 Podman 构建，标签为 v1.0"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--runtime)
            RUNTIME="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            usage
            ;;
    esac
done

# 检测运行时
detect_runtime() {
    if [ "$RUNTIME" = "auto" ]; then
        # 优先使用 Podman，其次 Docker
        if command -v podman &> /dev/null; then
            RUNTIME="podman"
            echo -e "${GREEN}✓ 检测到 Podman，使用 Podman 构建${NC}"
        elif command -v docker &> /dev/null; then
            RUNTIME="docker"
            echo -e "${GREEN}✓ 检测到 Docker，使用 Docker 构建${NC}"
        else
            echo -e "${RED}✗ 错误: 未找到 Docker 或 Podman${NC}"
            echo "请先安装 Docker 或 Podman"
            exit 1
        fi
    else
        if command -v "$RUNTIME" &> /dev/null; then
            echo -e "${GREEN}✓ 使用指定的运行时: $RUNTIME${NC}"
        else
            echo -e "${RED}✗ 错误: 未找到 $RUNTIME 命令${NC}"
            exit 1
        fi
    fi
}

# 检查运行时状态
check_runtime_status() {
    echo -e "${YELLOW}检查 $RUNTIME 状态...${NC}"

    if [ "$RUNTIME" = "podman" ]; then
        # Podman 可能需要启动虚拟机（macOS）
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if ! podman ps &> /dev/null; then
                echo -e "${YELLOW}Podman 虚拟机未运行，正在启动...${NC}"
                podman machine start &> /dev/null || true
                sleep 3
            fi
        fi
    elif [ "$RUNTIME" = "docker" ]; then
        # Docker 可能需要启动 Desktop（macOS）
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if ! docker ps &> /dev/null; then
                echo -e "${YELLOW}Docker 未运行，正在启动...${NC}"
                open -a Docker
                echo "等待 Docker 启动..."
                sleep 5
            fi
        fi
    fi

    # 验证连接
    if $RUNTIME ps &> /dev/null; then
        echo -e "${GREEN}✓ $RUNTIME 运行正常${NC}"
    else
        echo -e "${RED}✗ 无法连接到 $RUNTIME${NC}"
        exit 1
    fi
}

# 构建镜像
build_image() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}开始构建镜像${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "运行时: ${YELLOW}$RUNTIME${NC}"
    echo -e "镜像名: ${YELLOW}$FULL_IMAGE_NAME${NC}"
    echo ""

    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo -e "工作目录: ${YELLOW}$SCRIPT_DIR${NC}"
    echo ""

    # 构建镜像
    $RUNTIME build -t "$FULL_IMAGE_NAME" "$SCRIPT_DIR"

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}✓ 镜像构建成功！${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo -e "镜像: ${YELLOW}$FULL_IMAGE_NAME${NC}"
        echo ""
        echo "验证镜像:"
        $RUNTIME images | grep "$IMAGE_NAME"
        echo ""
        echo "使用镜像:"
        echo "  Docker: docker run -it $FULL_IMAGE_NAME /bin/bash"
        echo "  Podman: podman run -it $FULL_IMAGE_NAME /bin/bash"
    else
        echo ""
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}✗ 镜像构建失败${NC}"
        echo -e "${RED}========================================${NC}"
        exit 1
    fi
}

# 主流程
main() {
    echo -e "${GREEN}AgentMatrix 容器镜像构建工具${NC}"
    echo ""

    detect_runtime
    check_runtime_status
    build_image
}

# 执行主流程
main
