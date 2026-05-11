#!/bin/bash
# 自动化部署验证脚本
# 用法：bash deploy/verify.sh [ECS_IP]

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 如果提供了 IP 参数，使用远程 IP，否则使用 localhost
TARGET_HOST="${1:-localhost}"
API_URL="http://${TARGET_HOST}:8000"
WEB_URL="http://${TARGET_HOST}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署验证脚本${NC}"
echo -e "${GREEN}  目标: ${TARGET_HOST}${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

PASSED=0
FAILED=0

# 测试函数
test_step() {
    local name="$1"
    local command="$2"

    echo -n "${name}... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC}"
        ((FAILED++))
        return 1
    fi
}

# 1. 检查容器状态（仅本地）
if [ "$TARGET_HOST" = "localhost" ]; then
    echo -e "${YELLOW}[容器检查]${NC}"
    test_step "  容器运行状态" "docker-compose ps 2>/dev/null | grep -q 'Up'"
    echo ""
fi

# 2. 健康检查
echo -e "${YELLOW}[健康检查]${NC}"
test_step "  后端健康检查" "curl -sf ${API_URL}/api/v1/health"
test_step "  前端页面访问" "curl -sf ${WEB_URL}"
test_step "  API 文档访问" "curl -sf ${API_URL}/api/docs"
echo ""

# 3. API 功能测试
echo -e "${YELLOW}[API 功能测试]${NC}"

# 简单对话测试
echo -n "  简单对话测试... "
START_TIME=$(date +%s)
RESPONSE=$(curl -s -X POST ${API_URL}/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"你好","conversation_id":"verify-test-'$(date +%s)'"}' \
  2>/dev/null | head -1)

if echo "$RESPONSE" | grep -q "data:"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo -e "${GREEN}✓${NC} (${DURATION}s)"
    ((PASSED++))
else
    echo -e "${RED}✗${NC}"
    ((FAILED++))
fi

# RAG 测试
echo -n "  RAG 检索测试... "
START_TIME=$(date +%s)
RESPONSE=$(curl -s -X POST ${API_URL}/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"扫地机器人有哪些功能？","conversation_id":"verify-rag-'$(date +%s)'"}' \
  2>/dev/null | head -5)

if echo "$RESPONSE" | grep -q "data:"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo -e "${GREEN}✓${NC} (${DURATION}s)"
    ((PASSED++))
else
    echo -e "${RED}✗${NC}"
    ((FAILED++))
fi

echo ""

# 4. 资源检查（仅本地）
if [ "$TARGET_HOST" = "localhost" ]; then
    echo -e "${YELLOW}[资源占用]${NC}"

    if command -v docker &> /dev/null; then
        APP_MEM=$(docker stats --no-stream --format "{{.MemUsage}}" robot-vacuum-agent 2>/dev/null | awk '{print $1}' || echo "N/A")
        APP_CPU=$(docker stats --no-stream --format "{{.CPUPerc}}" robot-vacuum-agent 2>/dev/null || echo "N/A")

        echo "  App 容器内存: ${APP_MEM}"
        echo "  App 容器 CPU: ${APP_CPU}"
    fi

    echo ""
fi

# 5. 总结
echo -e "${GREEN}========================================${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}  验证通过！✓${NC}"
    echo -e "${GREEN}  通过: ${PASSED} 项${NC}"
else
    echo -e "${RED}  验证失败！✗${NC}"
    echo -e "${GREEN}  通过: ${PASSED} 项${NC}"
    echo -e "${RED}  失败: ${FAILED} 项${NC}"
fi
echo -e "${GREEN}========================================${NC}"
echo ""

# 访问信息
echo "访问地址："
echo "  前端: ${WEB_URL}"
echo "  API 文档: ${API_URL}/api/docs"
echo ""

# 常用命令提示
if [ "$TARGET_HOST" = "localhost" ]; then
    echo "常用命令："
    echo "  查看日志: docker-compose logs -f app"
    echo "  重启服务: docker-compose restart"
    echo "  资源监控: docker stats"
fi

exit $FAILED
