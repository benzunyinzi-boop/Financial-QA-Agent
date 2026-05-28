
"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from utils.logger_handler import logger


class RagSummarizeService(object):
    def __init__(self, kb_name: str = "public_kb"):
        self.kb_name = kb_name
        self.vector_store = VectorStoreService(kb_name=kb_name)
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self.prompt_template | self.model | StrOutputParser()

    def retriever_docs(self, query: str) -> list[Document]:
        try:
            return self.retriever.invoke(query)
        except Exception as e:
            if "no such table: collections" in str(e):
                logger.warning("[RAG检索]检测到chroma库异常，自动重建后重试一次")
                self.vector_store = VectorStoreService(kb_name=self.kb_name)
                self.retriever = self.vector_store.get_retriever()
                return self.retriever.invoke(query)
            raise e

    def rag_summarize(self, query: str) -> str:

        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService(kb_name="public_kb")

    print(rag.rag_summarize("重疾险等待期是多久"))
