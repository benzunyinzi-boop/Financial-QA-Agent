from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.config_handler import chroma_conf
from chromadb.config import Settings

from model.factory import embed_model

from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger

import os
import shutil


class VectorStoreService:
    def __init__(self, kb_name: str = "public_kb"):
        self.kb_name = kb_name
        self.kb_config = self._load_kb_config(kb_name)
        self.collection_name = self.kb_config["collection_name"]
        self.sub_dir = self.kb_config["sub_dir"]

        self.vector_store = self._create_vector_store()

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

        self._ensure_vector_store_ready()

    def _load_kb_config(self, kb_name: str) -> dict:
        kbs = chroma_conf.get("knowledge_bases", {})
        if kb_name not in kbs:
            raise ValueError(f"未配置的知识库：{kb_name}，可用：{list(kbs.keys())}")
        return kbs[kb_name]

    def _md5_store_path(self) -> str:
        return get_abs_path(f"md5_{self.kb_name}.txt")

    def _create_vector_store(self) -> Chroma:
        persist_dir = get_abs_path(chroma_conf["persist_directory"])
        return Chroma(
            collection_name=self.collection_name,
            embedding_function=embed_model,
            persist_directory=persist_dir,
            client_settings=Settings(
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=persist_dir,
            ),
        )

    def _reset_vector_store(self):
        # 注意：Chroma 多 collection 共享同一 persist_directory，重置时仅删除当前 collection
        try:
            self.vector_store._client.delete_collection(self.collection_name)
        except Exception as e:
            logger.warning(f"[向量库]删除 collection {self.collection_name} 失败：{str(e)}")
        self.vector_store = self._create_vector_store()

    def _ensure_vector_store_ready(self):
        """
        检查向量库是否可用：
        1) 若本地sqlite结构损坏（典型报错：no such table: collections），自动重建。
        2) 若集合为空，自动执行一次知识库加载。
        """
        try:
            count = self.vector_store._collection.count()
        except Exception as e:
            if "no such table: collections" in str(e):
                logger.warning("[向量库]检测到损坏的chroma库结构，自动重建并重新加载知识库")
                self._reset_vector_store()
                self.load_document()
                return
            raise e

        if count == 0:
            logger.info("[向量库]集合为空，开始首次加载知识库")
            self.load_document()

    def get_retriever(self, k: int = None):
        """
        :param k: 召回数量；不传则用 chroma.yml 里的默认 k
                  开启 rerank 时建议传更大的值（如 20）作为候选池
        """
        if k is None:
            k = chroma_conf["k"]
        return self.vector_store.as_retriever(search_kwargs={"k": k})

    def get_all_documents(self) -> list[Document]:
        """
        从 Chroma 集合里拉出所有文档（供 BM25 等关键词检索器构建内存索引）
        注意：百万级文档以上会有内存压力，那时应改用 Elasticsearch 等外部 BM25
        """
        try:
            result = self.vector_store._collection.get()
            texts = result.get("documents", []) or []
            metadatas = result.get("metadatas", []) or []
            return [
                Document(page_content=text, metadata=meta or {})
                for text, meta in zip(texts, metadatas)
            ]
        except Exception as e:
            logger.error(f"[向量库]拉取所有文档失败：{str(e)}", exc_info=True)
            return []

    def load_single_document(self, file_path: str, document_id: str) -> int:
        """
        加载单个文档到向量库
        :param file_path: 文件路径
        :param document_id: 文档 ID（用于后续删除）
        :return: 分块数量
        """
        def get_file_documents(read_path: str):
            if read_path.endswith("txt") or read_path.endswith("md"):
                return txt_loader(read_path)
            if read_path.endswith("pdf"):
                return pdf_loader(read_path)
            return []

        try:
            documents: list[Document] = get_file_documents(file_path)

            if not documents:
                logger.warning(f"[加载知识库]{file_path}内没有有效文本内容")
                return 0

            split_document: list[Document] = self.spliter.split_documents(documents)

            if not split_document:
                logger.warning(f"[加载知识库]{file_path}分片后没有有效文本内容")
                return 0

            # 在每个分块的 metadata 中添加 document_id 和 kb_name
            for i, doc in enumerate(split_document):
                doc.metadata["document_id"] = document_id
                doc.metadata["chunk_index"] = i
                doc.metadata["source_file"] = os.path.basename(file_path)
                doc.metadata["kb_name"] = self.kb_name

            # DashScope Embedding API 限制每批次最多 10 个文档
            batch_size = 10
            total_chunks = len(split_document)
            for i in range(0, total_chunks, batch_size):
                batch = split_document[i:i + batch_size]
                self.vector_store.add_documents(batch)
                logger.info(f"[加载知识库]已处理 {min(i + batch_size, total_chunks)}/{total_chunks} 个分块")

            logger.info(f"[加载知识库]{file_path} 内容加载成功，共 {total_chunks} 个分块")
            return total_chunks

        except Exception as e:
            logger.error(f"[加载知识库]{file_path}加载失败：{str(e)}", exc_info=True)
            raise e

    def delete_document(self, document_id: str):
        """
        删除指定文档的所有向量分块
        :param document_id: 文档 ID
        """
        try:
            # Chroma 通过 where 条件删除
            self.vector_store._collection.delete(
                where={"document_id": document_id}
            )
            logger.info(f"[删除知识库]文档 {document_id} 的向量已删除")
        except Exception as e:
            logger.error(f"[删除知识库]删除文档 {document_id} 失败：{str(e)}", exc_info=True)
            raise e

    def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        :return: None
        """

        md5_store_path = self._md5_store_path()

        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(md5_store_path):
                # 创建文件
                open(md5_store_path, "w", encoding="utf-8").close()
                return False            # md5 没处理过

            with open(md5_store_path, "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True     # md5 处理过

                return False            # md5 没处理过

        def save_md5_hex(md5_for_check: str):
            with open(md5_store_path, "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith("txt") or read_path.endswith("md"):
                return txt_loader(read_path)

            if read_path.endswith("pdf"):
                return pdf_loader(read_path)

            return []

        kb_data_path = os.path.join(get_abs_path(chroma_conf["data_path"]), self.sub_dir)
        if not os.path.exists(kb_data_path):
            logger.warning(f"[加载知识库]{kb_data_path} 目录不存在，跳过 {self.kb_name} 加载")
            return

        allowed_files_path: list[str] = listdir_with_allowed_type(
            kb_data_path,
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                continue

            try:
                documents: list[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                split_document: list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue

                # 将内容存入向量库（DashScope Embedding API 限制每批次最多 10 个）
                batch_size = 10
                for i in range(0, len(split_document), batch_size):
                    self.vector_store.add_documents(split_document[i:i + batch_size])

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # exc_info为True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)
                continue


if __name__ == '__main__':
    for kb in ["public_kb", "internal_kb"]:
        print(f"\n==== 测试 {kb} ====")
        vs = VectorStoreService(kb_name=kb)
        vs.load_document()

        retriever = vs.get_retriever()
        query = "重疾险等待期" if kb == "public_kb" else "销售误导红线"
        res = retriever.invoke(query)
        for r in res:
            print(r.metadata.get("source_file"), "|", r.page_content[:60])
            print("-"*20)
