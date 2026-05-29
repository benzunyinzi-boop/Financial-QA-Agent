#!/bin/bash
# 项目部署脚本 - 在 ECS 上执行
# 用法：./deploy.sh

set -e

PROJECT_DIR="/opt/Financial-QA-Agent"
REPO_URL="https://github.com/benzunyinzi-boop/Financial-QA-Agent.git"
BRANCH="main"

echo "=== 1. 克隆/更新代码 ==="
if [ -d "$PROJECT_DIR" ]; then
    echo "项目目录已存在，拉取最新代码..."
    cd $PROJECT_DIR
    git pull origin $BRANCH
else
    echo "克隆项目..."
    sudo mkdir -p /opt
    sudo git clone -b $BRANCH $REPO_URL $PROJECT_DIR
    sudo chown -R $USER:$USER $PROJECT_DIR
    cd $PROJECT_DIR
fi

echo "=== 2. 配置环境变量 ==="
if [ ! -f .env ]; then
    echo "创建 .env 文件..."
    cat > .env <<EOF
# DashScope API Key (必填)
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# 可选配置
LOG_LEVEL=INFO
EOF
    echo "⚠️  请编辑 .env 文件，填入真实的 DASHSCOPE_API_KEY"
    exit 1
fi

echo "=== 3. 安装后端依赖 ==="
python3.9 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== 4. 初始化向量数据库 ==="
python3 init_db.py

echo "=== 5. 构建前端 ==="
cd frontend
npm install
npm run build
cd ..

echo "=== 6. 配置 Nginx ==="
sudo cp deploy/nginx.conf /etc/nginx/sites-available/langchain-agent
sudo ln -sf /etc/nginx/sites-available/langchain-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

echo "=== 7. 配置 Supervisor ==="
sudo cp deploy/supervisor.conf /etc/supervisor/conf.d/langchain-agent.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart langchain-agent

echo "=== 部署完成 ==="
echo "访问 http://YOUR_ECS_IP 查看应用"
echo "查看日志: sudo supervisorctl tail -f langchain-agent"
