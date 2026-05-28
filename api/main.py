"""
FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import knowledge, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化双 Agent"""
    # 启动
    chat.initialize_agents()
    yield
    # 关闭（MemorySaver 无需清理）


app = FastAPI(
    title="安心保险智能客服 API",
    description="保险行业双角色 AI 客服系统（重疾险+医疗险）",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])


@app.get("/")
async def root():
    return {"message": "安心保险智能客服 API", "version": "0.2.0"}


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
