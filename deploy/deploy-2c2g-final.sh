#!/bin/bash
# 保险助手 - 2核2G ECS 一键部署脚本（最终版）
# 用法：curl -fsSL https://raw.githubusercontent.com/benzunyinzi-boop/Financial-QA-Agent/main/deploy/deploy-2c2g-final.sh | bash
#
# 前置条件：
#   1. 前端 dist 已在本地构建并上传到 ECS
#   2. 已有 DashScope API Key

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/opt/Financial-QA-Agent"
REPO_URL="https://github.com/benzunyinzi-boop/Financial-QA-Agent.git"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  保险助手智能客服 - 2核2G 部署${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 用户运行${NC}"
    echo "使用命令: sudo bash $0"
    exit 1
fi

# Step 1: 检查 Docker
echo -e "${GREEN}[1/6] 检查 Docker${NC}"
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
fi
if ! command -v docker-compose &> /dev/null; then
    echo "安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi
echo "Docker: $(docker --version)"
echo "Compose: $(docker-compose --version)"
echo ""

# Step 2: 配置 Swap（2核2G 必需）
echo -e "${GREEN}[2/6] 配置 Swap${NC}"
SWAP_SIZE=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$SWAP_SIZE" -lt 1024 ]; then
    echo -e "${YELLOW}当前 swap: ${SWAP_SIZE}MB，配置 2GB swap...${NC}"

    if [ -f /swapfile ]; then
        swapoff /swapfile 2>/dev/null || true
        rm -f /swapfile
    fi

    # 创建 swap
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile

    # 开机自动挂载
    if ! grep -q "^/swapfile" /etc/fstab; then
        echo "/swapfile none swap sw 0 0" >> /etc/fstab
    fi

    # 优化 swappiness
    sysctl vm.swappiness=10
    if ! grep -q "^vm.swappiness" /etc/sysctl.conf; then
        echo "vm.swappiness=10" >> /etc/sysctl.conf
    fi

    echo "Swap 配置完成: 2GB"
else
    echo "Swap 已配置: ${SWAP_SIZE}MB"
fi
free -h
echo ""

# Step 3: 克隆/更新代码
echo -e "${GREEN}[3/6] 获取项目代码${NC}"
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    echo "项目目录已存在，拉取最新代码..."
    git pull origin main || echo -e "${YELLOW}git pull 失败，继续使用本地代码${NC}"
else
    echo "克隆项目..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi
echo ""

# Step 4: 配置环境变量
echo -e "${GREEN}[4/6] 配置环境变量${NC}"
if [ ! -f .env ]; then
    echo -e "${YELLOW}请输入 DashScope API Key:${NC}"
    read -p "API Key: " api_key

    cat > .env <<EOF
DASHSCOPE_API_KEY=$api_key
LOG_LEVEL=INFO
EOF
    chmod 600 .env
    echo "已创建 .env"
else
    echo ".env 已存在，跳过"
fi
echo ""

# Step 5: 检查前端 dist
echo -e "${GREEN}[5/6] 检查前端构建产物${NC}"
if [ ! -d "frontend/dist" ] || [ -z "$(ls -A frontend/dist 2>/dev/null)" ]; then
    echo -e "${RED}错误：frontend/dist 目录不存在或为空！${NC}"
    echo ""
    echo "请在本地构建前端后上传："
    echo "  1. 本地: git clone $REPO_URL && cd Financial-QA-Agent"
    echo "  2. 本地: cd frontend && npm install && npm run build && cd .."
    echo "  3. 本地: tar -czf frontend-dist.tar.gz frontend/dist/"
    echo "  4. 本地: scp frontend-dist.tar.gz root@$(curl -s ifconfig.me):$PROJECT_DIR/"
    echo "  5. ECS:  cd $PROJECT_DIR && tar -xzf frontend-dist.tar.gz"
    echo "  6. ECS:  再次运行本脚本"
    exit 1
fi
DIST_SIZE=$(du -sh frontend/dist | cut -f1)
echo "frontend/dist: $DIST_SIZE ✓"
echo ""

# Step 6: 启动服务（首次启动会自动初始化数据库表和向量库）
echo -e "${GREEN}[6/6] 启动服务${NC}"
docker-compose -f docker-compose.lite.yml up -d --build

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

sleep 5
docker-compose -f docker-compose.lite.yml ps

echo ""
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_ECS_IP")
echo "访问地址:"
echo "  - 前端: http://$PUBLIC_IP:8090"
echo "  - API 文档: http://$PUBLIC_IP:8000/docs"
echo ""
echo -e "${YELLOW}首次启动会自动加载知识库（约 1-2 分钟），请稍等${NC}"
echo "可通过 'docker-compose -f docker-compose.lite.yml logs -f app' 查看初始化进度"
echo ""
echo "常用命令:"
echo "  查看日志: cd $PROJECT_DIR && docker-compose -f docker-compose.lite.yml logs -f"
echo "  重启服务: cd $PROJECT_DIR && docker-compose -f docker-compose.lite.yml restart"
echo "  停止服务: cd $PROJECT_DIR && docker-compose -f docker-compose.lite.yml down"
echo "  资源占用: docker stats"
echo ""
echo -e "${YELLOW}提示: 建议配置 HTTPS，参考 deploy/DEPLOY_2C2G_FINAL.md${NC}"
