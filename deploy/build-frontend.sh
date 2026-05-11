#!/bin/bash
# 本地构建前端脚本
# 用法：在你的本地开发机（Mac/Windows）上执行此脚本
# 原因：2核2G ECS 内存不够跑 npm run build（需要 1.2GB+）

set -e

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  前端本地构建脚本 (for 2核2G ECS)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误：未安装 Node.js，请先安装 Node.js 18+${NC}"
    echo "macOS: brew install node"
    echo "其他：https://nodejs.org/"
    exit 1
fi

echo -e "${GREEN}[1/4] Node.js 版本: $(node --version)${NC}"
echo ""

# 进入前端目录
cd frontend

echo -e "${GREEN}[2/4] 安装前端依赖...${NC}"
if [ ! -d "node_modules" ] || [ "$1" == "--clean" ]; then
    rm -rf node_modules package-lock.json
    npm install
else
    echo "node_modules 已存在，跳过（如需强制重装，使用 --clean 参数）"
fi
echo ""

echo -e "${GREEN}[3/4] 构建前端生产版本...${NC}"
npm run build

if [ ! -d "dist" ]; then
    echo -e "${RED}构建失败：dist 目录不存在${NC}"
    exit 1
fi

DIST_SIZE=$(du -sh dist | cut -f1)
echo -e "${GREEN}构建完成，dist 大小: $DIST_SIZE${NC}"
echo ""

cd ..

echo -e "${GREEN}[4/4] 打包 dist 用于上传...${NC}"
TAR_FILE="frontend-dist-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$TAR_FILE" frontend/dist/

PACKAGE_SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo -e "${GREEN}打包完成: $TAR_FILE ($PACKAGE_SIZE)${NC}"
echo ""

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  下一步：上传到 ECS${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "方式 1：上传 tar 包（推荐，快）"
echo "  scp $TAR_FILE root@YOUR_ECS_IP:/opt/robot-vacuum-customer-agent/"
echo "  # 然后在 ECS 上："
echo "  cd /opt/robot-vacuum-customer-agent"
echo "  tar -xzf $TAR_FILE"
echo ""
echo "方式 2：rsync 增量同步 dist（推荐更新时用）"
echo "  rsync -avz --delete frontend/dist/ root@YOUR_ECS_IP:/opt/robot-vacuum-customer-agent/frontend/dist/"
echo ""
echo "上传后，在 ECS 上执行："
echo "  docker-compose -f docker-compose.lite.yml up -d --build"
