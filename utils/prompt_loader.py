from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

def load_system_prompts():
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompts]在yaml配置项中没有main_prompt_path配置项")
        raise e

    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompts]解析系统提示词出错，{str(e)}")
        raise e


def load_rag_prompts():
    try:
        rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_prompts]在yaml配置项中没有rag_summarize_prompt_path配置项")
        raise e

    try:
        return open(rag_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompts]解析RAG提示词出错，{str(e)}")
        raise e


def load_report_prompts():
    try:
        report_prompt_path = get_abs_path(prompts_conf["report_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_report_prompts]在yaml配置项中没有report_prompt_path配置项")
        raise e

    try:
        return open(report_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompts]解析报告生成提示词出错，{str(e)}")
        raise e


def load_prompt_by_role(role: str):
    """根据角色加载对应提示词"""
    role_key_map = {
        "customer": "customer_main_prompt_path",
        "agent": "agent_main_prompt_path",
    }

    key = role_key_map.get(role)
    if not key:
        raise ValueError(f"未知角色：{role}，可用：{list(role_key_map.keys())}")

    try:
        prompt_path = get_abs_path(prompts_conf[key])
    except KeyError as e:
        logger.error(f"[load_prompt_by_role]在yaml配置项中没有{key}配置项")
        raise e

    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_prompt_by_role]解析{role}提示词出错，{str(e)}")
        raise e


if __name__=='__main__':
    print(load_prompt_by_role("customer"))
    print("\n" + "="*50 + "\n")
    print(load_prompt_by_role("agent"))

    