import os
from datetime import datetime
from utils.logger_handler import logger
from langchain_core.tools import tool

from rag.rag_service import RagSummarizeService
import random
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path

rag = RagSummarizeService()

user_ids = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010",]

external_data = {}


@tool
def rag_summarize(query: str) -> str:
    """从向量存储中检索参考资料"""
    try:
        return rag.rag_summarize(query)
    except Exception as e:
        logger.error(f"[rag_summarize]检索或总结失败：{str(e)}", exc_info=True)
        return "当前知识检索服务暂不可用（可能是网络或模型服务异常），请稍后重试。"


@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气，以消息字符串的形式返回"""
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风1级，AQI21，最近6小时降雨概率极低"


@tool
def get_user_location(dummy: str) -> str:
    """获取用户所在城市的名称，以纯字符串形式返回。入参可为任意占位字符串。"""
    return random.choice(["深圳", "合肥", "杭州"])


@tool
def get_user_id(dummy: str) -> str:
    """获取用户的ID，以纯字符串形式返回。入参可为任意占位字符串。"""
    return random.choice(user_ids)


@tool
def get_current_month(dummy: str) -> str:
    """获取当前月份，返回 YYYY-MM 格式字符串。入参可为任意占位字符串。"""
    return datetime.now().strftime("%Y-%m")


def generate_external_data():
    """
    {
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        ...
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data_path"])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")

                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }


@tool
def fetch_external_data(input_text: str) -> str:
    """从外部系统中获取指定用户在指定月份的使用记录。入参格式：user_id,month，例如：1001,2025-01"""
    generate_external_data()
    arr = input_text.split(",", 1)
    if len(arr) != 2:
        return "参数格式错误，请使用：user_id,month，例如：1001,2025-01"
    user_id = arr[0].strip()
    month = arr[1].strip()

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(f"[fetch_external_data]未能检索到用户：{user_id}在{month}的使用记录数据")
        return ""
#if __name__ =='__main__':
#    print=(fetch_external_data("1001","2025-01"))

@tool
def fill_context_for_report(dummy: str):
    """调用后触发报告生成场景（兼容单入参工具协议，入参可为任意占位字符串）。"""
    return "fill_context_for_report已调用"
