# 保险助手 - 2核2G 阿里云 ECS 部署指南

> 本文档专为 **2核2G** 配置的阿里云 ECS 优化，包含完整的部署流程和脚本。

## 📋 配置要求

| 项目 | 要求 |
|------|------|
| CPU | 2核 |
| 内存 | 2GB |
| 磁盘 | 40GB+ |
| 操作系统 | Ubuntu 20.04+ / Alibaba Cloud Linux 3 |
| 网络 | 公网 IP + 开放 80/443 端口 |

## ⚠️ 2核2G 特殊说明

2GB 内存运行 Docker + FastAPI + LLM 应用比较吃紧，必须做以下优化：

1. **配置 2GB Swap**：避免 OOM（内存溢出）
2. **前端本地构建**：ECS 上不跑 `npm build`（需要 1.2GB+ 峰值内存）
3. **使用 Dockerfile.lite**：跳过容器内前端构建阶段
4. **资源限制**：docker-compose 里限制容器内存上限
5. **单 worker 运行**：FastAPI 不开多进程

---

## 🚀 快速部署（3 步）

### 步骤 1：本地构建前端（在你的电脑上）

```bash
# 克隆项目
git clone https://github.com/benzunyinzi-boop/Financial-QA-Agent.git
cd Financial-QA-Agent

# 构建前端
cd frontend
npm install
npm run build
cd ..

# 打包 dist
tar -czf frontend-dist.tar.gz frontend/dist/
```

### 步骤 2：上传到 ECS

```bash
# 上传前端构建产物
scp frontend-dist.tar.gz root@YOUR_ECS_IP:/tmp/

# 或者用 rsync（更新时更快）
rsync -avz --delete frontend/dist/ root@YOUR_ECS_IP:/opt/Financial-QA-Agent/frontend/dist/
```

### 步骤 3：ECS 上一键部署

SSH 连接到 ECS 后执行：

```bash
# 下载并运行部署脚本
curl -fsSL https://raw.githubusercontent.com/benzunyinzi-boop/Financial-QA-Agent/main/deploy/deploy-2c2g-final.sh | bash
```

---

## 📝 手动部署（详细步骤）

如果一键脚本失败，按以下步骤手动部署。

### 1. 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证
docker --version
docker-compose --version
```

### 2. 配置 Swap（必需）

```bash
# 创建 2GB swap 文件
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 开机自动挂载
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 优化 swap 使用策略
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# 验证
free -h
```

### 3. 克隆项目

```bash
cd /opt
sudo git clone https://github.com/benzunyinzi-boop/Financial-QA-Agent.git
cd Financial-QA-Agent
```

### 4. 解压前端构建产物

```bash
# 如果用 scp 上传了 tar 包
tar -xzf /tmp/frontend-dist.tar.gz

# 验证
ls -lh frontend/dist/
```

### 5. 配置环境变量

```bash
cat > .env <<EOF
DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here
LOG_LEVEL=INFO
EOF

chmod 600 .env
```

### 6. 启动服务

```bash
docker-compose -f docker-compose.lite.yml up -d --build
```

> 首次启动时会自动初始化数据库表和向量库（约 1-2 分钟），无需手动执行额外的初始化命令。

### 7. 验证部署

```bash
# 查看容器状态
docker-compose -f docker-compose.lite.yml ps

# 查看日志（首次启动会看到知识库加载日志）
docker-compose -f docker-compose.lite.yml logs -f app

# 测试 API（通过 Nginx 转发，因为 8000 端口不再暴露到主机）
curl http://localhost:8090/api/v1/health

# 或直接进入容器测试
docker exec insurance-agent curl http://localhost:8000/api/v1/health

# 浏览器访问
# http://YOUR_ECS_IP:8090
```

---

## 🔧 配置文件说明

### docker-compose.lite.yml

已针对 2核2G 优化的 docker-compose 配置：

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.lite
    container_name: insurance-agent
    restart: unless-stopped
    # 后端不暴露到主机端口，仅通过 docker network 内部供 nginx 访问
    expose:
      - "8000"
    environment:
      - DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - PYTHONDONTWRITEBYTECODE=1
      - PYTHONUNBUFFERED=1
    volumes:
      - ./chroma_db:/app/chroma_db
      - ./logs:/app/logs
      - ./data:/app/data
    networks:
      - app-net
    # 资源限制（2核2G 适配）
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 1400M
        reservations:
          cpus: '0.5'
          memory: 800M
    # 日志轮转
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  nginx:
    image: nginx:alpine
    container_name: insurance-nginx
    restart: unless-stopped
    ports:
      - "8090:80"
    volumes:
      - ./deploy/nginx-docker.conf:/etc/nginx/conf.d/default.conf:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
    depends_on:
      - app
    networks:
      - app-net
    deploy:
      resources:
        limits:
          memory: 100M
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "2"

networks:
  app-net:
    driver: bridge
```

### Dockerfile.lite

跳过前端构建的精简 Dockerfile：

```dockerfile
FROM python:3.9-slim

# 配置阿里云镜像源
RUN sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list 2>/dev/null || true

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && rm -rf /var/lib/apt/lists/*

# 配置 PyPI 镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 确保 frontend/dist 存在
RUN if [ ! -d "/app/frontend/dist" ]; then \
      echo "ERROR: frontend/dist 不存在！请先构建前端" && exit 1; \
    fi

RUN mkdir -p /app/chroma_db /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "start_api.py"]
```

---

## 🛠️ 常用运维命令

### 查看状态

```bash
cd /opt/Financial-QA-Agent

# 容器状态
docker-compose -f docker-compose.lite.yml ps

# 资源占用
docker stats

# 系统资源
free -h
df -h
```

### 查看日志

```bash
# 实时日志
docker-compose -f docker-compose.lite.yml logs -f app

# 最近 100 行
docker-compose -f docker-compose.lite.yml logs --tail=100 app

# Nginx 日志
docker-compose -f docker-compose.lite.yml logs nginx
```

### 重启服务

```bash
# 重启所有容器
docker-compose -f docker-compose.lite.yml restart

# 只重启后端
docker-compose -f docker-compose.lite.yml restart app

# 只重启 Nginx
docker-compose -f docker-compose.lite.yml restart nginx
```

### 更新代码

```bash
cd /opt/Financial-QA-Agent

# 拉取最新代码
git pull origin main

# 如果前端有更新，重新上传 dist

# 重新构建并启动
docker-compose -f docker-compose.lite.yml up -d --build
```

### 停止服务

```bash
# 停止但保留容器
docker-compose -f docker-compose.lite.yml stop

# 停止并删除容器
docker-compose -f docker-compose.lite.yml down

# 停止并删除容器 + 数据卷（危险）
docker-compose -f docker-compose.lite.yml down -v
```

---

## 🐛 故障排查

### 问题 1：容器启动失败

```bash
# 查看详细日志
docker-compose -f docker-compose.lite.yml logs app

# 常见原因：
# 1. .env 文件不存在或 API Key 错误
# 2. frontend/dist 目录不存在
# 3. 端口被占用
```

### 问题 2：内存不足 / OOM

```bash
# 检查 swap
free -h

# 如果 swap 为 0，重新配置
sudo swapon /swapfile

# 查看容器内存占用
docker stats

# 降低资源限制（编辑 docker-compose.lite.yml）
# memory: 1400M → 1200M
```

### 问题 3：前端无法访问

```bash
# 检查 Nginx 容器
docker-compose -f docker-compose.lite.yml ps nginx

# 检查 dist 目录
ls -lh frontend/dist/

# 查看 Nginx 日志
docker-compose -f docker-compose.lite.yml logs nginx

# 测试后端 API
curl http://localhost:8000/api/v1/health
```

### 问题 4：API 调用失败

```bash
# 检查 API Key
cat .env

# 测试 DashScope 连通性
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"hi"}]}'
```

### 问题 5：磁盘空间不足

```bash
# 查看磁盘使用
df -h

# 清理 Docker 缓存
docker system prune -a

# 清理日志
sudo journalctl --vacuum-time=7d

# 清理旧的前端构建包
rm -f /opt/Financial-QA-Agent/frontend-dist-*.tar.gz
```

---

## 🔒 安全加固

### 1. 配置防火墙

```bash
# 启用 UFW
sudo ufw enable

# 开放必要端口
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8090/tcp  # Web 访问端口

# 查看状态
sudo ufw status
```

### 2. 配置 HTTPS（推荐）

```bash
# 安装 Certbot
sudo apt install -y certbot

# 申请证书（需要先配置域名解析）
sudo certbot certonly --standalone -d yourdomain.com

# 修改 docker-compose.lite.yml，添加证书挂载
# volumes:
#   - /etc/letsencrypt:/etc/nginx/ssl:ro

# 修改 nginx-docker.conf，启用 HTTPS 配置
```

### 3. 禁用 root SSH 登录

```bash
sudo vim /etc/ssh/sshd_config
# 设置 PermitRootLogin no
sudo systemctl restart sshd
```

---

## 📊 性能监控

### 资源监控

```bash
# 实时监控
htop

# Docker 容器资源
docker stats

# 磁盘 I/O
iostat -x 1
```

### 日志监控

```bash
# 查看错误日志
docker-compose -f docker-compose.lite.yml logs app | grep ERROR

# 统计请求量
docker-compose -f docker-compose.lite.yml logs nginx | grep "GET /api" | wc -l
```

---

## 📦 备份与恢复

### 备份向量数据库

```bash
cd /opt/Financial-QA-Agent
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz chroma_db/

# 上传到对象存储或其他服务器
```

### 恢复向量数据库

```bash
cd /opt/Financial-QA-Agent
docker-compose -f docker-compose.lite.yml stop app
tar -xzf chroma_backup_YYYYMMDD.tar.gz
docker-compose -f docker-compose.lite.yml start app
```

---

## 🎯 性能优化建议

1. **升级到 2核4G**：如果预算允许，多 2GB 内存体验会好很多
2. **使用 CDN**：前端静态资源走 CDN，减轻 ECS 压力
3. **启用 Gzip**：Nginx 配置 gzip 压缩，减少传输量
4. **定期清理日志**：避免磁盘占满
5. **监控告警**：配置内存/磁盘告警，提前发现问题

---

## 📮 技术支持

- GitHub Issues: https://github.com/benzunyinzi-boop/Financial-QA-Agent/issues
- Email: benzunyinzi@gmail.com

---

**祝部署顺利！** 🚀
