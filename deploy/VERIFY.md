# 部署验证清单

部署完成后，按照以下步骤验证服务是否正常运行。

---

## 1. 容器状态检查（30 秒）

### 1.1 检查容器是否启动

```bash
cd /opt/robot-vacuum-customer-agent

# 标准部署
docker-compose ps

# 2核2G 部署
docker-compose -f docker-compose.lite.yml ps
```

**预期输出**：
```
NAME                    STATUS              PORTS
robot-vacuum-agent      Up 2 minutes        0.0.0.0:8000->8000/tcp
robot-vacuum-nginx      Up 2 minutes        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

**状态说明**：
- ✅ `Up` - 正常运行
- ⚠️ `Restarting` - 反复重启，有问题
- ❌ `Exited` - 已退出，启动失败

### 1.2 查看容器日志

```bash
# 查看后端日志（最近 50 行）
docker-compose logs --tail=50 app

# 实时跟踪日志
docker-compose logs -f app
```

**正常日志示例**：
```
robot-vacuum-agent  | INFO:     Started server process [1]
robot-vacuum-agent  | INFO:     Waiting for application startup.
robot-vacuum-agent  | INFO:     Application startup complete.
robot-vacuum-agent  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

**异常日志关键词**：
- `ERROR` - 错误
- `CRITICAL` - 严重错误
- `Traceback` - Python 异常堆栈
- `Connection refused` - 连接失败
- `Out of memory` - 内存不足

---

## 2. 健康检查（1 分钟）

### 2.1 后端健康检查

```bash
# 在 ECS 上执行
curl http://localhost:8000/api/v1/health

# 或从本地测试（替换 YOUR_ECS_IP）
curl http://YOUR_ECS_IP:8000/api/v1/health
```

**预期输出**：
```json
{
  "status": "healthy",
  "timestamp": "2026-05-11T12:00:00.000Z"
}
```

### 2.2 Nginx 健康检查

```bash
curl -I http://localhost

# 或
curl -I http://YOUR_ECS_IP
```

**预期输出**：
```
HTTP/1.1 200 OK
Server: nginx/1.25.x
Content-Type: text/html
...
```

### 2.3 API 文档访问

浏览器访问：
```
http://YOUR_ECS_IP/api/docs
```

应该能看到 **FastAPI Swagger UI** 文档页面。

---

## 3. 功能测试（5 分钟）

### 3.1 测试简单聊天（无 RAG）

```bash
curl -N -X POST http://YOUR_ECS_IP/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好，请介绍一下你自己",
    "conversation_id": "test-001"
  }'
```

**预期输出**（流式返回）：
```
data: {"type":"token","content":"你"}
data: {"type":"token","content":"好"}
data: {"type":"token","content":"！"}
...
data: {"type":"done"}
```

**响应时间**：
- 首 token：< 2 秒
- 完整回答：3-5 秒

### 3.2 测试 RAG 检索

```bash
curl -N -X POST http://YOUR_ECS_IP/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "扫地机器人有哪些主要功能？",
    "conversation_id": "test-002"
  }'
```

**预期行为**：
1. Agent 会调用 `rag_summarize` 工具
2. 从知识库检索相关文档
3. 基于检索结果生成回答

**日志中应该看到**：
```
INFO: Tool called: rag_summarize
INFO: Retrieved 3 documents from knowledge base
```

### 3.3 测试多轮对话（记忆）

```bash
# 第一轮
curl -N -X POST http://YOUR_ECS_IP/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我叫张三",
    "conversation_id": "test-003"
  }'

# 第二轮（同一个 conversation_id）
curl -N -X POST http://YOUR_ECS_IP/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我叫什么名字？",
    "conversation_id": "test-003"
  }'
```

**预期**：第二轮应该回答"你叫张三"，证明记忆功能正常。

---

## 4. 前端测试（3 分钟）

### 4.1 访问前端页面

浏览器打开：
```
http://YOUR_ECS_IP
```

**检查项**：
- ✅ 页面能正常加载（不是 404 或 502）
- ✅ 左侧边栏显示"安心问答"
- ✅ 右侧聊天区域显示欢迎界面
- ✅ 底部输入框可以输入文字

### 4.2 发送测试消息

在输入框输入：
```
你好，请介绍一下你自己
```

**检查项**：
- ✅ 消息立即显示在聊天区域（用户消息）
- ✅ 出现"正在思考..."加载动画
- ✅ AI 回复逐字流式显示（不是一次性全部出现）
- ✅ 回复完成后加载动画消失
- ✅ 消息支持 Markdown 格式（加粗、列表等）

### 4.3 测试 RAG 功能

输入：
```
扫地机器人无法回充怎么办？
```

**检查项**：
- ✅ 回答基于知识库内容（不是瞎编）
- ✅ 回答结构清晰（分步骤说明）
- ✅ 响应时间 < 10 秒

### 4.4 测试对话历史

1. 刷新页面（F5）
2. 检查之前的对话是否还在

**预期**：对话历史应该保留（localStorage 持久化）

### 4.5 测试知识库管理

点击左侧边栏"知识库管理"：

**检查项**：
- ✅ 能看到已有文档列表
- ✅ 点击"上传文档"按钮能打开文件选择
- ✅ 上传 PDF/TXT 文件后能在列表中看到
- ✅ 点击删除按钮能删除文档

---

## 5. 性能测试（2 分钟）

### 5.1 响应时间测试

```bash
# 测试 10 次，计算平均响应时间
for i in {1..10}; do
  echo "Test $i:"
  time curl -s -X POST http://YOUR_ECS_IP/api/v1/chat/stream \
    -H "Content-Type: application/json" \
    -d '{"message":"你好","conversation_id":"perf-test"}' \
    > /dev/null
done
```

**预期响应时间**：
- 2核2G：2-5 秒
- 2核4G：1-3 秒
- 4核8G：1-2 秒

### 5.2 资源占用检查

```bash
# 查看容器资源占用
docker stats --no-stream

# 查看系统资源
free -h
df -h
```

**预期值（2核2G）**：
```
CONTAINER           CPU %    MEM USAGE / LIMIT     MEM %
robot-vacuum-agent  30-50%   800MB / 1.4GB        60%
robot-vacuum-nginx  <5%      20MB / 100MB         20%
```

**系统内存**：
```
               total        used        free
Mem:           1.8Gi       1.4Gi       200Mi
Swap:          2.0Gi        50Mi       1.9Gi
```

---

## 6. 安全检查（1 分钟）

### 6.1 检查 .env 权限

```bash
ls -la /opt/robot-vacuum-customer-agent/.env
```

**预期**：
```
-rw------- 1 root root 123 May 11 12:00 .env
```

权限必须是 `600`（只有 owner 可读写）。

### 6.2 检查防火墙

```bash
# Ubuntu/Debian
sudo ufw status

# CentOS/RHEL
sudo firewall-cmd --list-all
```

**预期开放端口**：
- 22 (SSH)
- 80 (HTTP)
- 443 (HTTPS，如果配置了）

**不应该开放**：
- 8000（FastAPI 端口，应该只通过 Nginx 访问）

### 6.3 检查敏感信息泄露

```bash
# 检查日志中是否有 API Key
docker-compose logs app | grep -i "sk-"
```

**预期**：不应该有任何输出（API Key 不应该出现在日志中）。

---

## 7. 常见问题排查

### 问题 1：容器反复重启

**症状**：`docker-compose ps` 显示 `Restarting`

**排查**：
```bash
# 查看最近的错误日志
docker-compose logs --tail=100 app | grep -i error

# 常见原因：
# 1. API Key 错误
cat .env | grep DASHSCOPE_API_KEY

# 2. 内存不足
free -h

# 3. 端口被占用
netstat -tlnp | grep 8000
```

### 问题 2：前端 404

**症状**：访问 `http://YOUR_ECS_IP` 显示 404

**排查**：
```bash
# 检查 Nginx 容器状态
docker-compose ps nginx

# 检查 frontend/dist 是否存在
ls -la frontend/dist/

# 检查 Nginx 配置
docker-compose exec nginx nginx -t

# 查看 Nginx 日志
docker-compose logs nginx
```

### 问题 3：API 调用超时

**症状**：前端一直显示"正在思考..."

**排查**：
```bash
# 测试后端是否响应
curl -v http://localhost:8000/api/v1/health

# 检查 DashScope API 连通性
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer $(grep DASHSCOPE_API_KEY .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"hi"}]}'

# 查看后端日志
docker-compose logs -f app
```

### 问题 4：RAG 检索无结果

**症状**：问知识库相关问题，回答"我不知道"

**排查**：
```bash
# 检查向量数据库是否初始化
ls -la chroma_db/

# 重新初始化
docker-compose run --rm app python init_db.py

# 检查知识库文档
ls -la data/
```

---

## 8. 验证通过标准

所有以下项都通过，才算部署成功：

- [ ] 容器状态：`Up`，无 `Restarting`
- [ ] 健康检查：`/api/v1/health` 返回 200
- [ ] 前端访问：能打开页面，无 404/502
- [ ] 简单对话：能正常回复，响应时间 < 5 秒
- [ ] RAG 检索：能基于知识库回答问题
- [ ] 多轮对话：能记住上下文
- [ ] 流式输出：回复逐字显示，不是一次性出现
- [ ] 资源占用：内存 < 1.5GB（2核2G 配置）
- [ ] 日志无错误：无 `ERROR` 或 `CRITICAL` 级别日志
- [ ] 安全检查：.env 权限 600，日志无 API Key

---

## 9. 性能基准参考

### 2核2G 配置

| 指标 | 预期值 |
|------|--------|
| 冷启动时间 | 30-60 秒 |
| 健康检查响应 | < 10ms |
| 简单问答（无 RAG）| 1-3 秒 |
| RAG 检索 + 回答 | 3-8 秒 |
| 并发能力 | 3-5 QPS |
| 内存占用 | 1.2-1.5GB |
| CPU 占用（空闲）| < 10% |
| CPU 占用（处理请求）| 30-60% |

### 2核4G 配置

| 指标 | 预期值 |
|------|--------|
| 冷启动时间 | 20-40 秒 |
| 简单问答 | 1-2 秒 |
| RAG 检索 + 回答 | 2-5 秒 |
| 并发能力 | 5-10 QPS |

### 4核8G 配置

| 指标 | 预期值 |
|------|--------|
| 冷启动时间 | 15-30 秒 |
| 简单问答 | 0.5-1.5 秒 |
| RAG 检索 + 回答 | 1-3 秒 |
| 并发能力 | 10-20 QPS |

---

## 10. 自动化验证脚本

创建一个验证脚本 `verify.sh`：

```bash
#!/bin/bash
# 自动验证脚本

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  部署验证脚本"
echo "=========================================="
echo ""

# 1. 检查容器状态
echo -n "1. 检查容器状态... "
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ 容器未运行${NC}"
    exit 1
fi

# 2. 健康检查
echo -n "2. 后端健康检查... "
if curl -sf http://localhost:8000/api/v1/health > /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ 健康检查失败${NC}"
    exit 1
fi

# 3. 前端访问
echo -n "3. 前端页面检查... "
if curl -sf http://localhost > /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ 前端无法访问${NC}"
    exit 1
fi

# 4. API 测试
echo -n "4. API 功能测试... "
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"你好","conversation_id":"verify-test"}' | head -1)
if echo "$RESPONSE" | grep -q "data:"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ API 响应异常${NC}"
    exit 1
fi

# 5. 资源检查
echo -n "5. 资源占用检查... "
MEM_USAGE=$(docker stats --no-stream --format "{{.MemUsage}}" robot-vacuum-agent | awk '{print $1}')
echo -e "${GREEN}✓${NC} (内存: $MEM_USAGE)"

echo ""
echo -e "${GREEN}=========================================="
echo -e "  所有检查通过！部署成功 ✓"
echo -e "==========================================${NC}"
```

**使用方法**：
```bash
cd /opt/robot-vacuum-customer-agent
bash verify.sh
```

---

## 总结

按照以上步骤验证后，如果所有检查都通过，说明部署成功！

**快速验证命令（3 步）**：
```bash
# 1. 检查容器
docker-compose ps

# 2. 健康检查
curl http://localhost:8000/api/v1/health

# 3. 浏览器访问
# http://YOUR_ECS_IP
```

如果遇到问题，参考"常见问题排查"章节，或查看详细日志：
```bash
docker-compose logs -f app
```
