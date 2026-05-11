"""
知识库管理路由
"""
import os
import hashlib
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database.connection import get_db
from api.database.models import Document
from api.schemas.knowledge import DocumentResponse, DocumentListResponse, ApiResponse
from rag.vector_store import VectorStoreService

router = APIRouter()

# 文件上传目录
UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def calculate_md5(file_content: bytes) -> str:
    """计算文件 MD5"""
    return hashlib.md5(file_content).hexdigest()


@router.post("/upload", response_model=ApiResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传文档并向量化
    支持格式：txt, pdf, md
    """
    # 检查文件类型
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".txt", ".pdf", ".md"]:
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 txt/pdf/md")

    # 读取文件内容
    content = await file.read()
    file_size = len(content)
    file_md5 = calculate_md5(content)

    # 检查是否已存在（MD5 去重）
    existing = db.query(Document).filter(Document.md5 == file_md5).first()
    if existing:
        return ApiResponse(
            code=1,
            message="文档已存在（MD5 重复）",
            data={"document_id": existing.id}
        )

    # 生成文档 ID 和存储路径
    doc_id = str(uuid.uuid4())
    storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file.filename}")

    # 保存文件
    with open(storage_path, "wb") as f:
        f.write(content)

    # 创建数据库记录
    document = Document(
        id=doc_id,
        filename=file.filename,
        file_type=file_ext[1:],  # 去掉点号
        size_bytes=file_size,
        md5=file_md5,
        status="indexing",
        storage_path=storage_path
    )
    db.add(document)
    db.commit()

    # 向量化（同步执行，生产环境应改为异步任务）
    try:
        vector_service = VectorStoreService()
        chunk_count = vector_service.load_single_document(storage_path, doc_id)

        # 更新状态
        document.status = "indexed"
        document.chunk_count = chunk_count
        db.commit()

        return ApiResponse(
            code=0,
            message="上传成功",
            data={
                "document_id": doc_id,
                "filename": file.filename,
                "chunk_count": chunk_count
            }
        )
    except Exception as e:
        # 向量化失败
        document.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"向量化失败: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取文档列表
    """
    offset = (page - 1) * page_size

    total = db.query(Document).count()
    documents = db.query(Document)\
        .order_by(Document.created_at.desc())\
        .offset(offset)\
        .limit(page_size)\
        .all()

    return DocumentListResponse(
        total=total,
        documents=[DocumentResponse.from_orm(doc) for doc in documents]
    )


@router.delete("/documents/{document_id}", response_model=ApiResponse)
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    删除文档（同时删除向量库中的分块）
    """
    # 查询文档
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除向量库中的分块
    try:
        vector_service = VectorStoreService()
        vector_service.delete_document(document_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除向量失败: {str(e)}")

    # 删除文件
    if os.path.exists(document.storage_path):
        os.remove(document.storage_path)

    # 删除数据库记录
    db.delete(document)
    db.commit()

    return ApiResponse(
        code=0,
        message="删除成功",
        data={"document_id": document_id}
    )


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    获取知识库统计信息
    """
    total_docs = db.query(Document).count()
    total_chunks = db.query(Document).with_entities(
        db.func.sum(Document.chunk_count)
    ).scalar() or 0

    indexed_docs = db.query(Document).filter(Document.status == "indexed").count()

    return ApiResponse(
        code=0,
        message="ok",
        data={
            "total_documents": total_docs,
            "total_chunks": int(total_chunks),
            "indexed_documents": indexed_docs
        }
    )
