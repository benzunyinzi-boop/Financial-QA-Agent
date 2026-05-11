#!/bin/bash
# 2核2G ECS 一键部署脚本
# 前置条件：前端 dist 已经提前在本地构建好并上传到 /opt/robot-vacuum-customer-agent/frontend/dist/
#
# 完整流程：
#   1. 在本地: bash deploy/build-frontend.sh
#   2. 上传 dist 到 ECS
#   3. 在 ECS 上运行此脚本

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/opt/robot-vacuum-customer-agent"
REPO_URL="https://github.com/benzunyinzi-boop/robot-vacuum-customer-agent.git"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  扫地机器人智能客服 - 2核2G 部署${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 用户运行${NC}"
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
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi
echo "Docker: $(docker --version)"
echo "Compose: $(docker-compose --version)"
echo ""

# Step 2: 检查 swap
echo -e "${GREEN}[2/6] 检查 Swap${NC}"
SWAP_SIZE=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$SWAP_SIZE" -lt 1024 ]; then
    echo -e "${YELLOW}当前 swap: ${SWAP_SIZE}MB，建议至少 2GB${NC}"
    read -p "现在配置 2GB swap？(Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if [ -f "$PROJECT_DIR/deploy/setup-swap.sh" ]; then
            bash "$PROJECT_DIR/deploy/setup-swap.sh"
        else
            # 内联实现 swap 配置
            fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
            chmod 600 /swapfile
            mkswap /swapfile
            swapon /swapfile
            echo "/swapfile none swap sw 0 0" >> /etc/fstab
            sysctl vm.swappiness=10
        fi
    fi
else
    echo "Swap 已配置: ${SWAP_SIZE}MB"
fi
echo ""

# Step 3: 克隆/更新代码
echo -e "${GREEN}[3/6] 获取项目代码${NC}"
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    git pull origin main || echo -e "${YELLOW}git pull 失败，继续使用本地代码${NC}"
else
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi
echo ""

# Step 4: 配置环境变量
echo -e "${GREEN}[4/6] 配置环境变量${NC}"
if [ ! -f .env ]; then
    read -p "请输入 DashScope API Key: " api_key
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
    echo "  1. 本地: git clone $REPO_URL && cd robot-vacuum-customer-agent"
    echo "  2. 本地: bash deploy/build-frontend.sh"
    echo "  3. 本地: scp frontend-dist-*.tar.gz root@$(curl -s ifconfig.me):$PROJECT_DIR/"
    echo "  4. ECS:  cd $PROJECT_DIR && tar -xzf frontend-dist-*.tar.gz"
    echo "  5. ECS:  再次运行本脚本"
    exit 1
fi
DIST_SIZE=$(du -sh frontend/dist | cut -f1)
echo "frontend/dist: $DIST_SIZE ✓"
echo ""

# Step 6: 启动服务
echo -e "${GREEN}[6/6] 启动服务${NC}"

# 检查向量库是否已初始化
if [ ! -d "chroma_db" ] || [ -z "$(ls -A chroma_db 2>/dev/null)" ]; then
    echo "初始化向量数据库（首次运行，约 1-2 分钟）..."
    docker-compose -f docker-compose.lite.yml run --rm app python init_db.py
fi

echo "启动容器..."
docker-compose -f docker-compose.lite.yml up -d --build

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

sleep 3
docker-compose -f docker-compose.lite.yml ps

echo ""
echo "访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_ECS_IP')"
echo ""
echo "常用命令："
echo "  查看日志: cd $PROJECT_DIR && docker-compose -f docker-compose.lite.yml logs -f"
echo "  重启:    cd $PROJECT_DIR && docker-compose -f docker-compose.lite.yml restart"
echo "  资源占用: docker stats"
