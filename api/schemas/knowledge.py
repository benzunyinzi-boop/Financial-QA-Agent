"""
Pydantic 数据模型（请求/响应 schema）
"""
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class DocumentBase(BaseModel):
    """文档基础模型"""
    filename: str
    file_type: str
    size_bytes: int


class DocumentCreate(DocumentBase):
    """创建文档请求"""
    md5: str
    storage_path: str


class DocumentResponse(DocumentBase):
    """文档响应模型"""
    id: str
    md5: str
    chunk_count: int
    status: str
    storage_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int
    documents: list[DocumentResponse]


class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 0
    message: str = "ok"
    data: Optional[dict] = None
