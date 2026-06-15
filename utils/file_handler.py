import os,hashlib
from utils.logger_handler import logger

from langchain_core.documents import Document
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader

def get_file_md5_hex(filepath:str):         # 获取文件的md5的十六进制字符串
    if not os.path.exists(filepath):
        logger.error(f"[MD5计算]文件{filepath}不存在")
        return
    if not os.path.isfile(filepath):
        logger.error(f"[MD5计算]路径{filepath}不是文件")
        return

    md5_obj = hashlib.md5()
    chunk_size=4096     # 4KB分片，避免文件过大爆内存
    try:
            with open(filepath, "rb")as f:  # 必须二进制读取
                while chunk:=f.read(chunk_size):
                    md5_obj.update(chunk)

            md5_hex=md5_obj.hexdigest()
            return md5_hex
    except Exception as  e:
        logger.error(f"计算文件{filepath}md5失败，{str(e)}")
        return None

def listdir_with_allowed_type(path:str,allowed_types:tuple[str]):   # 返回文件夹内的文件列表（允许的文件后缀）
    files= []
    if not os.path.isdir(path):
        logger.error(f"[lisdir_with_allowed_type]{path}不是文件夹")
        return allowed_types

    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path,f))
    return tuple(files)

def pdf_loader(filepath: str, passwd: str = None) -> list[Document]:
    # PyMuPDFLoader 相比 PyPDFLoader 能更好地保留表格、多栏布局和页眉页脚结构
    return PyMuPDFLoader(filepath, password=passwd or "").load()


def pdf_markdown_loader(filepath: str) -> list[Document]:
    """
    PDF → Markdown 加载器（保留章节标题结构，便于 MarkdownHeaderTextSplitter 切分）
    适用：标题层级清晰的 PDF（如规范化的保险条款）
    备注：扫描件 / 排版混乱的 PDF 用纯文本 pdf_loader 反而更好
    """
    try:
        import pymupdf4llm
    except ImportError:
        logger.warning("[PDF→Markdown]缺少 pymupdf4llm，降级为 pdf_loader")
        return pdf_loader(filepath)

    try:
        md_text = pymupdf4llm.to_markdown(filepath)
    except Exception as e:
        logger.warning(f"[PDF→Markdown]{filepath} 转 Markdown 失败：{e}，降级为 pdf_loader")
        return pdf_loader(filepath)

    if not md_text or not md_text.strip():
        return pdf_loader(filepath)

    return [Document(
        page_content=md_text,
        metadata={"source": filepath, "original_format": "markdown"},
    )]


def pptx_loader(filepath: str) -> list[Document]:
    """
    PPT 加载器：每页 slide 一个 Document，提取标题/正文/备注/表格
    PPT 一页就是一个完整语义单元，不再做字符级切分
    """
    try:
        from pptx import Presentation
    except ImportError:
        logger.error("[PPT加载]缺少依赖 python-pptx，请安装：pip install python-pptx")
        return []

    docs: list[Document] = []
    try:
        prs = Presentation(filepath)
    except Exception as e:
        logger.error(f"[PPT加载]打开 {filepath} 失败：{e}")
        return []

    for idx, slide in enumerate(prs.slides):
        slide_no = idx + 1

        # 1) 主体文字（标题、正文、形状内文字）
        text_parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                tf_text = "\n".join(
                    p.text for p in shape.text_frame.paragraphs if p.text.strip()
                )
                if tf_text.strip():
                    text_parts.append(tf_text)

        # 2) 表格（结构化提取为简单文本）
        table_parts = []
        for shape in slide.shapes:
            if shape.has_table:
                rows = []
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    rows.append(" | ".join(cells))
                if rows:
                    table_parts.append("\n".join(rows))

        # 3) 备注（销售话术 PPT 的备注通常是干货）
        notes = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()

        # 拼接
        content_blocks = []
        if text_parts:
            content_blocks.append("\n".join(text_parts))
        if table_parts:
            content_blocks.append("【表格】\n" + "\n\n".join(table_parts))
        if notes:
            content_blocks.append("【备注】\n" + notes)

        page_content = "\n\n".join(content_blocks).strip()
        if not page_content:
            continue

        docs.append(Document(
            page_content=page_content,
            metadata={
                "page": slide_no,           # 与 PyMuPDFLoader 的 page 字段对齐
                "slide_index": slide_no,    # PPT 专属字段
            },
        ))

    logger.info(f"[PPT加载]{filepath} 提取 {len(docs)}/{len(prs.slides)} 页有效内容")
    return docs


def txt_loader(filepath:str)->list[Document]:

    return TextLoader(filepath,encoding="utf-8").load()
