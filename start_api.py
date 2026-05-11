"""
FastAPI 应用启动脚本
初始化数据库并启动服务
"""
import os
from dotenv import load_dotenv
import uvicorn
from api.database.connection import init_db

# 加载 .env 文件中的环境变量
load_dotenv()

if __name__ == "__main__":
    # 检查必需的环境变量
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("错误：未找到 DASHSCOPE_API_KEY 环境变量")
        print("请创建 .env 文件并设置 DASHSCOPE_API_KEY")
        print("参考 .env.example 文件")
        exit(1)

    # 初始化数据库表
    print("正在初始化数据库...")
    init_db()
    print("数据库初始化完成")

    # 启动 FastAPI 服务
    print("启动 FastAPI 服务...")
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
