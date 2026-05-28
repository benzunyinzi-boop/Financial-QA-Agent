"""
保险问答 Agent 工具集（MVP 版本）

工具分组：
- 通用工具：search_knowledge, get_current_date
- 客户工具：get_my_policies, get_my_policy_detail, get_my_claim_progress
- 客服工具：query_any_policy, query_customer_profile, compare_products, check_compliance
"""
import json
import os
from datetime import datetime
from langchain_core.tools import tool
from rag.rag_router import RagRouter
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


# ============ 通用工具（客户+客服共用）============

def make_search_knowledge(role: str):
    """闭包：绑定 role 到工具内部，避免 LLM 自己传 role 参数"""
    @tool
    def search_knowledge(query: str) -> str:
        """检索保险产品、条款、流程、FAQ 等参考资料。query 为贴合问题的关键词。"""
        try:
            router = RagRouter()
            return router.search(query, role=role)
        except Exception as e:
            logger.error(f"[search_knowledge]检索失败：{str(e)}", exc_info=True)
            return f"检索失败：{str(e)}"
    return search_knowledge


@tool
def get_current_date(dummy: str) -> str:
    """获取今天日期，用于计算保单剩余有效期等。dummy 为占位参数。"""
    return datetime.now().strftime("%Y-%m-%d")


# ============ 客户工具（仅客户端可用）============

# Mock 当前登录用户
CURRENT_USER_ID = "C001"


def _load_mock_json(filename: str):
    path = get_abs_path(f"data/mock/{filename}")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@tool
def get_my_policies(dummy: str) -> str:
    """查询当前用户名下所有保单。dummy 为占位参数。"""
    try:
        data = _load_mock_json("policies.json")
        my_policies = [p for p in data.get("policies", []) if p["customer_id"] == CURRENT_USER_ID]

        if not my_policies:
            return "您当前没有保单。"

        result = f"您共有 {len(my_policies)} 份保单：\n"
        for p in my_policies:
            result += f"- 保单号：{p['policy_no']} | 产品：{p['product_name']} | 状态：{p['status']} | 保额：{p['sum_insured']}元\n"
        return result
    except Exception as e:
        logger.error(f"[get_my_policies]查询失败：{str(e)}", exc_info=True)
        return f"查询失败：{str(e)}"


@tool
def get_my_policy_detail(policy_no: str) -> str:
    """查询指定保单详情（必须是当前用户名下的）。"""
    try:
        data = _load_mock_json("policies.json")
        policy = next((p for p in data.get("policies", []) if p["policy_no"] == policy_no), None)

        if not policy:
            return f"未找到保单号 {policy_no}。"

        if policy["customer_id"] != CURRENT_USER_ID:
            return "出于隐私保护，您只能查询本人名下的保单。"

        result = f"""
保单号：{policy['policy_no']}
产品名称：{policy['product_name']}
状态：{policy['status']}
生效日期：{policy['start_date']}
到期日期：{policy['end_date']}
保障期限：{policy['term']}
缴费期间：{policy['payment_period']}
年缴保费：{policy['premium']}元
保额：{policy['sum_insured']}元
受益人：{policy['beneficiary']}
下次缴费日：{policy['next_payment_date']}
"""
        return result.strip()
    except Exception as e:
        logger.error(f"[get_my_policy_detail]查询失败：{str(e)}", exc_info=True)
        return f"查询失败：{str(e)}"


@tool
def get_my_claim_progress(claim_no: str) -> str:
    """查询当前用户的理赔进度。"""
    try:
        data = _load_mock_json("claims.json")
        claim = next((c for c in data.get("claims", []) if c["claim_no"] == claim_no), None)

        if not claim:
            return f"未找到理赔工单 {claim_no}。"

        if claim["customer_id"] != CURRENT_USER_ID:
            return "出于隐私保护，您只能查询本人的理赔记录。"

        result = f"""
理赔工单号：{claim['claim_no']}
关联保单：{claim['policy_no']}
理赔类型：{claim['claim_type']}
状态：{claim['status']}
出险日期：{claim['accident_date']}
报案日期：{claim['report_date']}
申请金额：{claim['claim_amount']}元
"""
        if claim['payout_amount'] is not None:
            result += f"赔付金额：{claim['payout_amount']}元\n"
        if claim['payout_date']:
            result += f"赔付日期：{claim['payout_date']}\n"
        result += f"备注：{claim['remark']}"

        return result.strip()
    except Exception as e:
        logger.error(f"[get_my_claim_progress]查询失败：{str(e)}", exc_info=True)
        return f"查询失败：{str(e)}"


# ============ 客服工具（仅客服端可用）============

@tool
def query_any_policy(policy_no: str) -> str:
    """查询任意保单（无归属限制，留审计）。客服专用。"""
    try:
        data = _load_mock_json("policies.json")
        policy = next((p for p in data.get("policies", []) if p["policy_no"] == policy_no), None)

        if not policy:
            return f"未找到保单号 {policy_no}。"

        result = f"""
保单号：{policy['policy_no']}
客户姓名：{policy['customer_name']}（ID: {policy['customer_id']}）
产品名称：{policy['product_name']}
状态：{policy['status']}
生效日期：{policy['start_date']}
到期日期：{policy['end_date']}
保障期限：{policy['term']}
缴费期间：{policy['payment_period']}
年缴保费：{policy['premium']}元
保额：{policy['sum_insured']}元
受益人：{policy['beneficiary']}
下次缴费日：{policy['next_payment_date']}
"""
        return result.strip()
    except Exception as e:
        logger.error(f"[query_any_policy]查询失败：{str(e)}", exc_info=True)
        return f"查询失败：{str(e)}"


@tool
def query_customer_profile(customer_id: str) -> str:
    """查询客户画像（保单数、理赔次数、投诉记录、风险等级）。客服专用。"""
    try:
        data = _load_mock_json("customers.json")
        customer = next((c for c in data.get("customers", []) if c["customer_id"] == customer_id), None)

        if not customer:
            return f"未找到客户 {customer_id}。"

        result = f"""
客户ID：{customer['customer_id']}
姓名：{customer['name']}
性别：{customer['gender']}
年龄：{customer['age']}
手机号：{customer['phone_masked']}
身份证：{customer['id_card_masked']}
风险等级：{customer['risk_level']}
保单数量：{customer['policy_count']}
理赔次数：{customer['claim_count']}
投诉次数：{customer['complaint_count']}
VIP等级：{customer['vip_level']}
备注：{customer['remark']}
"""
        return result.strip()
    except Exception as e:
        logger.error(f"[query_customer_profile]查询失败：{str(e)}", exc_info=True)
        return f"查询失败：{str(e)}"


@tool
def compare_products(product_codes: str) -> str:
    """多产品横向对比，入参逗号分隔产品代码，如 CI-DEMO-001,CI-DEMO-002。客服专用。"""
    try:
        codes = [c.strip() for c in product_codes.split(",")]
        data = _load_mock_json("products.json")
        products = [p for p in data.get("products", []) if p["product_code"] in codes]

        if not products:
            return f"未找到产品代码：{product_codes}"

        result = "产品对比：\n"
        for p in products:
            result += f"\n【{p['product_code']}】{p['product_name']}\n"
            result += f"- 类别：{p['category']}\n"
            result += f"- 描述：{p['description']}\n"
            result += f"- 投保年龄：{p['min_age']}-{p['max_age']}岁\n"
            result += f"- 等待期：{p['waiting_period_days']}天\n"
            result += f"- 保费示例：{p['annual_premium_example']}\n"

        return result.strip()
    except Exception as e:
        logger.error(f"[compare_products]对比失败：{str(e)}", exc_info=True)
        return f"对比失败：{str(e)}"


@tool
def check_compliance(scenario: str) -> str:
    """合规风险检查，传入客服打算说的话或操作描述。客服专用。"""
    try:
        router = RagRouter()
        # 直接查内部库的合规红线
        result = router.search_single_kb(f"合规检查：{scenario}", kb_name="internal_kb")
        return f"【合规检查结果】\n{result}"
    except Exception as e:
        logger.error(f"[check_compliance]检查失败：{str(e)}", exc_info=True)
        return f"合规检查失败：{str(e)}"


# ============ 工具集构建函数 ============

def build_tools_for_role(role: str):
    """根据角色返回对应工具集"""
    base_tools = [
        make_search_knowledge(role),
        get_current_date,
    ]

    if role == "customer":
        return base_tools + [
            get_my_policies,
            get_my_policy_detail,
            get_my_claim_progress,
        ]
    elif role == "agent":
        return base_tools + [
            query_any_policy,
            query_customer_profile,
            compare_products,
            check_compliance,
        ]
    else:
        raise ValueError(f"未知角色：{role}")


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    print("=== 测试客户工具 ===")
    print(get_my_policies.invoke("dummy"))
    print("\n" + get_my_policy_detail.invoke("P20240001"))

    print("\n=== 测试客服工具 ===")
    print(query_any_policy.invoke("P20240005"))
    print("\n" + query_customer_profile.invoke("C002"))
