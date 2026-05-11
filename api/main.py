"""
FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import knowledge, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 Agent"""
    # 启动
    chat.initialize_agent()
    yield
    # 关闭（MemorySaver 无需清理）


app = FastAPI(
    title="智扫通智能客服 API",
    description="扫地机器人垂直领域 AI 客服系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 前端开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])


@app.get("/")
async def root():
    return {"message": "智扫通智能客服 API", "version": "0.1.0"}


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
