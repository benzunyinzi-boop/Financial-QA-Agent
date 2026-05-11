#!/bin/bash
# ECS 上配置 swap 交换空间脚本
# 适用于 2核2G ECS，添加 2GB swap 避免 OOM
# 用法：sudo bash setup-swap.sh

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
echo -e "${GREEN}  配置 swap 交换空间 (2核2G ECS)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查是否已有 swap
CURRENT_SWAP=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$CURRENT_SWAP" -gt 0 ]; then
    echo -e "${YELLOW}检测到已有 swap: ${CURRENT_SWAP}MB${NC}"
    read -p "是否继续添加新的 swap？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "取消操作"
        exit 0
    fi
fi

# 检查磁盘空间
FREE_SPACE=$(df -m / | awk 'NR==2 {print $4}')
if [ "$FREE_SPACE" -lt 3000 ]; then
    echo -e "${RED}警告：根分区剩余空间不足 3GB（当前 ${FREE_SPACE}MB），可能无法创建 2GB swap${NC}"
    read -p "是否继续？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

SWAP_SIZE="2G"
SWAP_FILE="/swapfile"

echo -e "${GREEN}[1/5] 创建 ${SWAP_SIZE} swap 文件: ${SWAP_FILE}${NC}"
if [ -f "$SWAP_FILE" ]; then
    swapoff "$SWAP_FILE" 2>/dev/null || true
    rm -f "$SWAP_FILE"
fi

# 使用 fallocate（快），失败则用 dd（慢但兼容性好）
if ! fallocate -l $SWAP_SIZE $SWAP_FILE 2>/dev/null; then
    echo "fallocate 不可用，改用 dd（较慢，约 1-2 分钟）..."
    dd if=/dev/zero of=$SWAP_FILE bs=1M count=2048 status=progress
fi

echo -e "${GREEN}[2/5] 设置权限${NC}"
chmod 600 $SWAP_FILE

echo -e "${GREEN}[3/5] 格式化为 swap${NC}"
mkswap $SWAP_FILE

echo -e "${GREEN}[4/5] 启用 swap${NC}"
swapon $SWAP_FILE

echo -e "${GREEN}[5/5] 配置开机自动挂载${NC}"
if ! grep -q "^$SWAP_FILE" /etc/fstab; then
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
    echo "已添加到 /etc/fstab"
else
    echo "/etc/fstab 已有配置，跳过"
fi

# 优化 swap 使用策略（降低使用倾向，优先用物理内存）
echo -e "${GREEN}[额外] 优化 swappiness${NC}"
sysctl vm.swappiness=10
if ! grep -q "^vm.swappiness" /etc/sysctl.conf; then
    echo "vm.swappiness=10" >> /etc/sysctl.conf
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Swap 配置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
free -h
echo ""
swapon --show
