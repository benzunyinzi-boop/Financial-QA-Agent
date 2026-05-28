# 阿里云 ECS 部署完整指南

本文档提供将安心问答保险智能问答系统部署到阿里云 ECS 的完整方案。

## 📋 目录

- [部署方案对比](#部署方案对比)
- [方案 A：Docker 部署（推荐）](#方案-a-docker-部署推荐)
- [方案 B：传统部署](#方案-b-传统部署)
- [部署后配置](#部署后配置)
- [常见问题](#常见问题)

---

## 部署方案对比

| 特性 | Docker 部署 | 传统部署 |
|------|------------|---------|
| **部署难度** | ⭐ 简单（5 分钟） | ⭐⭐⭐ 复杂（30 分钟） |
| **环境隔离** | ✅ 完全隔离 | ❌ 可能冲突 |
| **依赖管理** | ✅ 自动处理 | ❌ 手动安装 |
| **版本回滚** | ✅ 一键回滚 | ❌ 需要手动 |
| **资源控制** | ✅ 精确限制 | ❌ 难以控制 |
| **迁移成本** | ✅ 低（打包镜像） | ❌ 高（重新配置） |
| **适用场景** | 生产环境、快速部署 | 学习研究、定制化需求 |

**推荐：Docker 部署** 🐳

---

## 方案 A: Docker 部署（推荐）

### 前置要求

1. **阿里云 ECS**
   - 配置：2核4G 起步（推荐 4核8G）
   - 磁盘：40GB+
   - 操作系统：Ubuntu 20.04+ / CentOS 8+
   - 已分配公网 IP

2. **DashScope API Key**
   - 申请地址：https://dashscope.console.aliyun.com/

### 一键部署（5 分钟）

```bash
# 1. 连接到 ECS
ssh root@YOUR_ECS_IP

# 2. 下载并运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/LangChain-ReAct-Agent/main/deploy/quick-deploy.sh | bash

# 3. 按提示输入 DashScope API Key

# 4. 等待部署完成，访问 http://YOUR_ECS_IP
```

### 手动部署步骤

如果一键脚本失败，可以手动执行以下步骤：

#### 1. 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

#### 2. 克隆项目

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/LangChain-ReAct-Agent.git
cd LangChain-ReAct-Agent
```

#### 3. 配置环境变量

```bash
# 创建 .env 文件
cat > .env <<EOF
DASHSCOPE_API_KEY=sk-your-api-key-here
LOG_LEVEL=INFO
EOF

chmod 600 .env
```

#### 4. 初始化向量数据库

```bash
docker-compose run --rm app python init_db.py
```

#### 5. 启动服务

```bash
docker-compose up -d --build
```

#### 6. 验证部署

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 测试 API
curl http://localhost/api/v1/health

# 浏览器访问
# http://YOUR_ECS_IP
```

### Docker 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新代码
git pull origin main
docker-compose up -d --build

# 备份向量数据库
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz chroma_db/
```

详细文档：[deploy/DOCKER_DEPLOY.md](deploy/DOCKER_DEPLOY.md)

---

## 方案 B: 传统部署

### 前置要求

同 Docker 部署，但需要额外安装：
- Python 3.9+
- Node.js 18+
- Nginx
- Supervisor

### 部署步骤

#### 1. 环境初始化

```bash
# 下载初始化脚本
wget https://raw.githubusercontent.com/YOUR_USERNAME/LangChain-ReAct-Agent/main/deploy/setup_ecs.sh
chmod +x setup_ecs.sh
./setup_ecs.sh
```

#### 2. 克隆项目

```bash
cd /opt
sudo git clone https://github.com/YOUR_USERNAME/LangChain-ReAct-Agent.git langchain-react-agent
sudo chown -R $USER:$USER langchain-react-agent
cd langchain-react-agent
```

#### 3. 配置环境变量

```bash
cat > .env <<EOF
DASHSCOPE_API_KEY=sk-your-api-key-here
LOG_LEVEL=INFO
EOF
chmod 600 .env
```

#### 4. 安装后端依赖

```bash
python3.9 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. 初始化向量数据库

```bash
python init_db.py
```

#### 6. 构建前端

```bash
cd frontend
npm install
npm run build
cd ..
```

#### 7. 配置 Nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/langchain-agent
sudo ln -sf /etc/nginx/sites-available/langchain-agent /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

#### 8. 配置 Supervisor

```bash
sudo cp deploy/supervisor.conf /etc/supervisor/conf.d/langchain-agent.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start langchain-agent
```

#### 9. 验证部署

```bash
# 查看服务状态
sudo supervisorctl status

# 查看日志
sudo supervisorctl tail -f langchain-agent

# 测试 API
curl http://localhost/api/v1/health
```

### 传统部署常用命令

```bash
# 查看服务状态
sudo supervisorctl status langchain-agent

# 启动/停止/重启
sudo supervisorctl start langchain-agent
sudo supervisorctl stop langchain-agent
sudo supervisorctl restart langchain-agent

# 查看日志
sudo supervisorctl tail -f langchain-agent

# 更新代码
cd /opt/langchain-react-agent
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
sudo supervisorctl restart langchain-agent
```

详细文档：[deploy/README.md](deploy/README.md)

---

## 部署后配置

### 1. 配置 HTTPS（强烈推荐）

#### 使用 Let's Encrypt 免费证书

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 申请证书（替换为你的域名）
sudo certbot --nginx -d yourdomain.com

# 证书会自动续期
sudo systemctl status certbot.timer
```

#### Docker 部署的 HTTPS 配置

```bash
# 1. 停止 Nginx 容器
docker-compose stop nginx

# 2. 申请证书
sudo certbot certonly --standalone -d yourdomain.com

# 3. 修改 docker-compose.yml，取消注释 SSL 卷挂载
# volumes:
#   - /etc/letsencrypt:/etc/nginx/ssl:ro

# 4. 修改 deploy/nginx-docker.conf，启用 HTTPS 配置

# 5. 重启服务
docker-compose up -d
```

### 2. 配置防火墙

```bash
# 启用防火墙
sudo ufw enable

# 开放必要端口
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS

# 查看状态
sudo ufw status
```

### 3. 配置域名解析

在你的域名服务商（如阿里云）配置 DNS A 记录：

```
类型: A
主机记录: @ 或 www
记录值: YOUR_ECS_PUBLIC_IP
TTL: 600
```

### 4. 配置日志轮转

```bash
# 创建日志轮转配置
sudo tee /etc/logrotate.d/langchain-agent <<EOF
/var/log/supervisor/langchain-agent.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0640 www-data www-data
}
EOF
```

### 5. 配置定期备份

```bash
# 编辑 crontab
sudo crontab -e

# 添加每天凌晨 2 点备份向量数据库
0 2 * * * tar -czf /backup/chroma_$(date +\%Y\%m\%d).tar.gz /opt/langchain-react-agent/chroma_db
```

---

## 性能优化

### 1. 启用 Gzip 压缩

编辑 Nginx 配置，在 `http` 块中添加：

```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
```

### 2. 配置 FastAPI 多进程

修改 `start_api.py`：

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # 根据 CPU 核心数调整
        reload=False,
    )
```

### 3. Docker 资源限制

编辑 `docker-compose.yml`：

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## 监控与运维

### 1. 查看资源使用

```bash
# 系统资源
htop

# Docker 容器资源
docker stats

# 磁盘使用
df -h
```

### 2. 查看日志

```bash
# Docker 部署
docker-compose logs -f app

# 传统部署
sudo supervisorctl tail -f langchain-agent

# Nginx 日志
sudo tail -f /var/log/nginx/langchain-agent-access.log
sudo tail -f /var/log/nginx/langchain-agent-error.log
```

### 3. 健康检查

```bash
# API 健康检查
curl http://localhost/api/v1/health

# 测试流式接口
curl -N -X POST http://localhost/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
```

---

## 常见问题

### Q1: 服务无法启动

**Docker 部署：**
```bash
# 查看日志
docker-compose logs app

# 检查配置
docker-compose config

# 重新构建
docker-compose build --no-cache app
docker-compose up -d
```

**传统部署：**
```bash
# 查看日志
sudo supervisorctl tail langchain-agent

# 手动启动测试
cd /opt/langchain-react-agent
source venv/bin/activate
python start_api.py
```

### Q2: 前端无法访问

```bash
# 检查 Nginx 状态
sudo systemctl status nginx

# 测试配置
sudo nginx -t

# 查看错误日志
sudo tail -f /var/log/nginx/error.log
```

### Q3: API 调用失败

```bash
# 检查 API Key
cat .env

# 测试 DashScope API
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"hi"}]}'
```

### Q4: 端口被占用

```bash
# 查看端口占用
sudo lsof -i :8000
sudo lsof -i :80

# 杀死进程
sudo kill -9 PID
```

### Q5: 磁盘空间不足

```bash
# 查看磁盘使用
df -h

# 清理 Docker 镜像和容器
docker system prune -a

# 清理日志
sudo journalctl --vacuum-time=7d
```

---

## 安全加固

### 1. 禁用 root SSH 登录

```bash
sudo vim /etc/ssh/sshd_config
# 设置 PermitRootLogin no
sudo systemctl restart sshd
```

### 2. 配置 SSH 密钥认证

```bash
# 本地生成密钥对
ssh-keygen -t rsa -b 4096

# 上传公钥到 ECS
ssh-copy-id user@YOUR_ECS_IP

# 禁用密码登录
sudo vim /etc/ssh/sshd_config
# 设置 PasswordAuthentication no
sudo systemctl restart sshd
```

### 3. 安装 fail2ban（防暴力破解）

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 部署检查清单

部署前请参考：[deploy/CHECKLIST.md](deploy/CHECKLIST.md)

---

## 相关文档

- [Docker 部署详细指南](deploy/DOCKER_DEPLOY.md)
- [传统部署详细指南](deploy/README.md)
- [部署检查清单](deploy/CHECKLIST.md)
- [项目 README](README.md)

---

## 技术支持

如遇问题，请：
1. 查看日志文件
2. 参考常见问题章节
3. 提交 GitHub Issue

---

**祝部署顺利！** 🚀
