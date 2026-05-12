"""
yml
k : V

"""



import os
import yaml
from utils.path_tool import get_abs_path


def load_rag_config(config_path: str = get_abs_path("config/rag.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_chroma_config(config_path: str = get_abs_path("config/chroma.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_prompts_config(config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_agent_config(config_path: str = get_abs_path("config/agent.yml"), encoding: str = "utf-8"):
    """
    加载 Agent 配置，根据 ENV 环境变量选择对应环境（development/testing/production）
    默认：development
    """
    with open(config_path, "r", encoding=encoding) as f:
        full_config = yaml.load(f, Loader=yaml.FullLoader)

    env = os.getenv("ENV", "development").lower()
    if env not in full_config:
        env = "development"
    return full_config[env]


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
agent_conf = load_agent_config()
prompts_conf = load_prompts_config()

if __name__ == '__main__':
    print(agent_conf["external_data_path"])  # 输出对应配置
