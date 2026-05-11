from abc import ABC, abstractmethod
from typing import Optional, Union
import os

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import ChatOpenAI

from utils.config_handler import rag_conf


# DashScope 的 OpenAI 兼容端点
# 参考：https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope
DASHSCOPE_OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Union[Embeddings, BaseChatModel]]:
        pass


class ChatModelFactory(BaseModelFactory):
    """
    使用 OpenAI 兼容协议调用 DashScope。
    相比 ChatTongyi：
      - 修复了流式 tool_calls 的 'name' KeyError bug
      - 原生支持 tool_calls 流式增量，与 LangGraph create_react_agent 完美兼容
      - 性能更优（SSE 传输）
    """
    def generator(self) -> BaseChatModel:
        return ChatOpenAI(
            model=rag_conf["chat_model_name"],
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=DASHSCOPE_OPENAI_BASE_URL,
            temperature=0.1,
            streaming=True,
            timeout=30,
        )


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Embeddings:
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])


# 全局单例
chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()
