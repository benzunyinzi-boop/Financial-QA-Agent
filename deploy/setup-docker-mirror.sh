#!/bin/bash
# 配置 Docker 镜像加速器（国内 ECS 必备）
# 用法：sudo bash deploy/setup-docker-mirror.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 或 sudo 运行${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  配置 Docker 镜像加速器（国内）${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误：Docker 未安装${NC}"
    exit 1
fi

# 创建 Docker 配置目录
mkdir -p /etc/docker

# 备份现有配置
if [ -f /etc/docker/daemon.json ]; then
    cp /etc/docker/daemon.json /etc/docker/daemon.json.bak.$(date +%Y%m%d_%H%M%S)
    echo "已备份现有配置"
fi

# 配置多个国内镜像源（容错）
cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev",
    "https://docker.chenby.cn",
    "https://docker.unsee.tech",
    "https://docker.1ms.run"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

echo -e "${GREEN}已写入镜像加速配置${NC}"

# 重启 Docker
echo -e "${YELLOW}重启 Docker 服务...${NC}"
systemctl daemon-reload
systemctl restart docker

sleep 2

# 验证
echo ""
echo -e "${GREEN}验证配置：${NC}"
docker info | grep -A 10 "Registry Mirrors:" || echo "未找到 Registry Mirrors 配置"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  配置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
