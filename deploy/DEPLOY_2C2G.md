# 2核2G ECS 优化部署指南

> 针对阿里云 2核2G 轻量级 ECS 的优化部署方案。
> 如果你用的是 4G+ 内存的 ECS，直接用 [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md) 即可。

## 为什么 2核2G 需要特殊配置？

### 内存占用分析

| 组件 | 占用 | 说明 |
|------|------|------|
| Ubuntu 系统 | ~300MB | 基础服务 |
| Docker daemon | ~150MB | 容器运行时 |
| Python + LangChain 运行时 | ~900MB | FastAPI + LangGraph + Chroma |
| **前端构建 (npm run build)** | **~1.5GB** | ⚠️ **主要瓶颈** |
| Nginx | ~20MB | 反向代理 |
| **峰值总计** | **~2.9GB** | 2G 内存 + swap 才够 |

### 核心优化策略

1. **本地构建前端** - 不在 ECS 上执行 `npm run build`
2. **添加 swap** - 给系统留缓冲空间
3. **单 worker 运行** - 避免多进程占用
4. **资源限制** - Docker 容器内存上限

---

## 部署流程（4 步，约 15 分钟）

### Step 1：本地构建前端（约 2 分钟）

**在你的 Mac/Windows 本地开发机上执行：**

```bash
# 克隆项目到本地
git clone https://github.com/benzunyinzi-boop/robot-vacuum-customer-agent.git
cd robot-vacuum-customer-agent

# 运行构建脚本
bash deploy/build-frontend.sh
```

脚本会：
- 检查 Node.js 是否安装
- 进入 `frontend/` 目录安装依赖
- 执行 `npm run build`
- 打包 `dist/` 为 `frontend-dist-YYYYMMDD.tar.gz`

**预期输出**：
```
构建完成，dist 大小: 1.5M
打包完成: frontend-dist-20260511.tar.gz (380K)
```

### Step 2：ECS 初始化（约 5 分钟）

**SSH 连接到 ECS：**

```bash
ssh root@YOUR_ECS_IP
```

**2.1 安装 Docker 和 Docker Compose**

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 验证
docker --version
docker-compose --version
```

**2.2 配置 swap（重要！）**

```bash
# 克隆项目（只克隆，不构建）
cd /opt
git clone https://github.com/benzunyinzi-boop/robot-vacuum-customer-agent.git
cd robot-vacuum-customer-agent

# 运行 swap 配置脚本
sudo bash deploy/setup-swap.sh
```

脚本会：
- 创建 2GB swap 文件（/swapfile）
- 设置开机自动挂载
- 优化 swappiness=10（优先用物理内存）

**验证 swap**：
```bash
free -h
# 应该能看到 Swap: 2.0Gi
```

### Step 3：上传前端 dist 到 ECS（约 30 秒）

**在本地执行**：

```bash
# 方式 A：SCP 上传 tar 包
scp frontend-dist-*.tar.gz root@YOUR_ECS_IP:/opt/robot-vacuum-customer-agent/

# 然后在 ECS 上解压
ssh root@YOUR_ECS_IP
cd /opt/robot-vacuum-customer-agent
tar -xzf frontend-dist-*.tar.gz
rm frontend-dist-*.tar.gz
ls -la frontend/dist/   # 验证
```

**方式 B：rsync（推荐，增量同步，更新时用）**

```bash
rsync -avz --delete \
  frontend/dist/ \
  root@YOUR_ECS_IP:/opt/robot-vacuum-customer-agent/frontend/dist/
```

### Step 4：在 ECS 上启动服务（约 5 分钟）

**在 ECS 上执行**：

```bash
cd /opt/robot-vacuum-customer-agent

# 配置 .env
cat > .env <<EOF
DASHSCOPE_API_KEY=sk-your-api-key-here
LOG_LEVEL=INFO
EOF
chmod 600 .env

# 初始化向量数据库（首次部署需要，约 1-2 分钟）
docker-compose -f docker-compose.lite.yml run --rm app python init_db.py

# 使用轻量版 compose 启动
docker-compose -f docker-compose.lite.yml up -d --build

# 查看状态
docker-compose -f docker-compose.lite.yml ps

# 查看日志
docker-compose -f docker-compose.lite.yml logs -f
```

**访问应用**：
```
http://YOUR_ECS_IP
```

---

## 资源使用情况

部署完成后，正常运行时的资源占用：

```bash
# 查看容器资源占用
docker stats --no-stream
```

**预期值**：

| 容器 | 内存 | CPU |
|------|------|-----|
| robot-vacuum-agent (Python) | 800MB - 1.2GB | <50% |
| robot-vacuum-nginx | ~20MB | <5% |

```bash
# 系统整体
free -h
```

**预期值**：
```
               total        used        free      shared  buff/cache   available
Mem:           1.8Gi       1.4Gi       100Mi       5.0Mi       300Mi       250Mi
Swap:          2.0Gi        50Mi       1.9Gi
```

---

## 常用命令

### 日常运维

```bash
# 查看日志
docker-compose -f docker-compose.lite.yml logs -f app

# 重启服务
docker-compose -f docker-compose.lite.yml restart

# 停止服务
docker-compose -f docker-compose.lite.yml down

# 查看资源占用
docker stats
```

### 更新代码流程

**后端代码更新**（改了 Python 代码）：

```bash
# 在 ECS 上
cd /opt/robot-vacuum-customer-agent
git pull origin main
docker-compose -f docker-compose.lite.yml up -d --build
```

**前端代码更新**（改了 React 代码）：

```bash
# 在本地
cd robot-vacuum-customer-agent
git pull origin main
bash deploy/build-frontend.sh

# 同步到 ECS
rsync -avz --delete \
  frontend/dist/ \
  root@YOUR_ECS_IP:/opt/robot-vacuum-customer-agent/frontend/dist/

# 在 ECS 上重启 Nginx（或热重载）
ssh root@YOUR_ECS_IP 'cd /opt/robot-vacuum-customer-agent && docker-compose -f docker-compose.lite.yml restart nginx'
```

---

## 故障排查

### 问题 1：Docker 构建时 OOM

**症状**：`docker-compose up -d --build` 时被 kill

**原因**：即使跳过了 npm 构建，pip install 也需要内存

**解决**：
```bash
# 先确保 swap 已启用
free -h

# 如果 swap 不够，临时再加 1G
sudo dd if=/dev/zero of=/swapfile2 bs=1M count=1024
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2
```

### 问题 2：容器频繁重启

**症状**：`docker-compose ps` 显示 Restarting

**查看原因**：
```bash
docker-compose -f docker-compose.lite.yml logs --tail=50 app
```

**常见原因**：
- 内存超限：调低 docker-compose.lite.yml 中的 `memory: 1400M`
- DashScope API Key 错误：检查 .env 文件
- Chroma 数据库损坏：`rm -rf chroma_db && docker-compose run --rm app python init_db.py`

### 问题 3：响应慢

**原因**：2核2G 性能有限，LLM 调用本身 1-3s

**优化**：
- 换小模型：`config/rag.yml` 改为 `qwen-turbo`（比 qwen-plus 快 2x）
- 降低检索 Top-K：`config/rag.yml` 的 `top_k: 2`
- 前端启用 gzip（已在 Nginx 配置中启用）

### 问题 4：磁盘满了

**清理**：
```bash
# 清理 Docker
docker system prune -a -f

# 清理日志
docker-compose -f docker-compose.lite.yml logs --tail=0 > /dev/null
journalctl --vacuum-time=3d

# 查看磁盘
df -h
```

---

## 升级到 2核4G 的路径

如果业务跑起来后想升级配置：

```bash
# 1. 阿里云控制台停止 ECS → 升级配置 → 重启

# 2. 删除 swap（可选，4G 内存通常够了）
sudo swapoff /swapfile
sudo rm /swapfile
sudo sed -i '/swapfile/d' /etc/fstab

# 3. 切换回标准 Dockerfile
cd /opt/robot-vacuum-customer-agent
docker-compose down
docker-compose up -d --build  # 使用标准 docker-compose.yml
```

---

## 性能基准（2核2G 实测）

| 指标 | 数值 |
|------|------|
| 冷启动时间 | ~40s |
| 健康检查响应 | <10ms |
| 简单问答响应（无 RAG）| 1-2s |
| RAG 检索 + 回答 | 3-5s |
| 并发能力 | ~5 QPS |
| 每日最大请求量（估算）| ~10万次 |

**适用场景**：
- ✅ 个人演示/学习
- ✅ 小规模内部使用（<50 用户/天）
- ✅ MVP 原型验证
- ⚠️ 中等规模生产（建议升级 2核4G 或 4核8G）

---

## 附：成本参考

**阿里云 2核2G 配置（2026 价格）**：
- 按量付费：约 0.3 元/小时（约 200 元/月）
- 包年包月：约 100-150 元/月
- 突发性能实例：更便宜，适合低负载

**DashScope 模型调用**：
- qwen-turbo：0.002 元/千 tokens（推荐 2核2G 使用）
- qwen-plus：0.004 元/千 tokens
- qwen-max：0.02 元/千 tokens

**月成本估算（100 用户/天）**：
- ECS: 100-200 元
- LLM: 20-50 元
- **总计：约 150-250 元/月**
