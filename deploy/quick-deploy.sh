#!/bin/bash
# 一键部署脚本 - Docker 版本
# 用法：curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/LangChain-ReAct-Agent/main/deploy/quick-deploy.sh | bash

set -e

echo "=========================================="
echo "  保险助手智能客服 - 一键部署脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 用户运行此脚本${NC}"
    echo "使用命令: sudo bash $0"
    exit 1
fi

# 配置变量
PROJECT_DIR="/opt/Financial-QA-Agent"
REPO_URL="https://github.com/benzunyinzi-boop/Financial-QA-Agent.git"

echo -e "${GREEN}步骤 1/6: 检查系统环境${NC}"
# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    echo "检测到操作系统: $OS"
else
    echo -e "${RED}无法检测操作系统${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}步骤 2/6: 安装 Docker${NC}"
if ! command -v docker &> /dev/null; then
    echo "Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker 安装完成"
else
    echo "Docker 已安装: $(docker --version)"
fi

echo ""
echo -e "${GREEN}步骤 3/6: 安装 Docker Compose${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose 未安装，正在安装..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose 安装完成"
else
    echo "Docker Compose 已安装: $(docker-compose --version)"
fi

echo ""
echo -e "${GREEN}步骤 4/6: 克隆项目代码${NC}"
if [ -d "$PROJECT_DIR" ]; then
    echo "项目目录已存在，拉取最新代码..."
    cd $PROJECT_DIR
    git pull origin main
else
    echo "克隆项目..."
    git clone $REPO_URL $PROJECT_DIR
    cd $PROJECT_DIR
fi

echo ""
echo -e "${GREEN}步骤 5/6: 配置环境变量${NC}"
if [ ! -f .env ]; then
    echo -e "${YELLOW}请输入 DashScope API Key:${NC}"
    read -p "API Key: " api_key

    cat > .env <<EOF
DASHSCOPE_API_KEY=$api_key
LOG_LEVEL=INFO
EOF
    chmod 600 .env
    echo "环境变量配置完成"
else
    echo ".env 文件已存在，跳过配置"
fi

echo ""
echo -e "${GREEN}步骤 6/6: 启动服务（首次启动会自动初始化数据库表和向量库）${NC}"
docker-compose up -d --build

echo ""
echo -e "${GREEN}=========================================="
echo "  部署完成！"
echo "==========================================${NC}"
echo ""
echo "服务状态:"
docker-compose ps
echo ""
echo "访问地址:"
echo "  - 前端: http://$(curl -s ifconfig.me)"
echo "  - API 文档: http://$(curl -s ifconfig.me)/api/docs"
echo ""
echo "常用命令:"
echo "  - 查看日志: cd $PROJECT_DIR && docker-compose logs -f"
echo "  - 重启服务: cd $PROJECT_DIR && docker-compose restart"
echo "  - 停止服务: cd $PROJECT_DIR && docker-compose down"
echo ""
echo -e "${YELLOW}提示: 如需配置 HTTPS，请参考 deploy/DOCKER_DEPLOY.md${NC}"
