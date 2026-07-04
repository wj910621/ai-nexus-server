"""
记忆增强模块
自动从对话中提取事实、更新用户画像、压缩超长历史
"""

import json
import re
from typing import List, Dict
from datetime import datetime

from config import settings
from memory import get_memory, save_memory, get_profile, set_profile
from logger import logger


# 简单规则提取：用于快速、零成本识别常见事实
_RULES = [
    (r"我[叫是]?(\S+?)(?:先生|女士)?[,，。]", "name"),
    (r"我?住?(?:在|于)([\u4e00-\u9fa5]{2,10}(?:市|县|区))", "city"),
    (r"我?的?工作[是为]?(.+?)[,，。]", "job"),
    (r"我?喜欢(.+?)[,，。]", "preference"),
]


def _extract_facts_by_rule(text: str) -> Dict[str, str]:
    """基于正则快速提取常见事实"""
    facts = {}
    for pattern, key in _RULES:
        for match in re.finditer(pattern, text):
            value = match.group(1).strip()
            if value and len(value) < 50:
                facts[key] = value
    return facts


def _call_llm_for_facts(messages: List[Dict]) -> Dict[str, str]:
    """调用 LLM 从对话中提取关键事实"""
    try:
        from openai import OpenAI
        from config import settings

        if not settings.deepseek_api_key:
            return {}

        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )

        conversation = "\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')}" 
            for m in messages[-6:]  # 只看最近 6 条
        ])

        prompt = f"""从以下对话中提取关于用户的关键事实。
只输出 JSON 对象，不要有任何其他文字。
如果没有任何新事实，输出空对象 {{}}。

可用字段：name（姓名）、city（城市）、job（职业）、preference（偏好）、habit（习惯）、goal（目标）、other（其他）。

对话：
{conversation}
"""
        response = client.chat.completions.create(
            model=settings.online_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            timeout=30
        )
        content = response.choices[0].message.content.strip()
        # 清理可能的 markdown 代码块
        content = content.strip("`").strip()
        if content.startswith("json"):
            content = content[4:].strip()

        facts = json.loads(content)
        if not isinstance(facts, dict):
            return {}
        return {k: str(v) for k, v in facts.items() if v}
    except Exception as e:
        logger.warning(f"LLM 事实提取失败：{e}")
        return {}


def extract_facts(messages: List[Dict]) -> Dict[str, str]:
    """结合规则和 LLM 提取事实"""
    facts = {}

    # 先走规则提取
    for m in messages:
        if m.get("role") == "user":
            facts.update(_extract_facts_by_rule(m.get("content", "")))

    # 再走 LLM 提取补充
    llm_facts = _call_llm_for_facts(messages)
    facts.update(llm_facts)

    return facts


def update_user_profile(facts: Dict[str, str]):
    """将提取的事实写入用户画像"""
    if not facts:
        return

    for key, value in facts.items():
        old = get_profile(key)
        if old != value:
            set_profile(key, value)
            logger.info(f"更新用户画像：{key} = {value}")


def get_profile_summary() -> str:
    """将用户画像格式化为字符串，供 system prompt 使用"""
    keys = ["name", "city", "job", "preference", "habit", "goal", "other"]
    parts = []
    for key in keys:
        value = get_profile(key)
        if value:
            parts.append(f"{key}: {value}")

    if not parts:
        return ""

    return "【用户画像】\n" + "\n".join(parts)


def should_summarize(messages: List[Dict]) -> bool:
    """判断是否需要压缩历史"""
    # 只统计非系统消息
    non_system = [m for m in messages if m.get("role") != "system"]
    return len(non_system) > settings.max_history * 2


def _call_llm_for_summary(messages: List[Dict]) -> str:
    """调用 LLM 生成对话摘要"""
    try:
        from openai import OpenAI

        if not settings.deepseek_api_key:
            return ""

        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )

        conversation = "\n".join([
            f"{m.get('role')}: {m.get('content', '')}"
            for m in messages
        ])

        prompt = f"""请将以下对话压缩成一段摘要，保留关键事实和用户需求，不超过 200 字。
摘要应使用第三人称。

对话：
{conversation}
"""
        response = client.chat.completions.create(
            model=settings.online_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"LLM 摘要生成失败：{e}")
        return ""


def summarize_old_messages(messages: List[Dict]) -> List[Dict]:
    """压缩旧对话：保留系统提示和最近 N 条，中间部分替换为摘要"""
    system = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    keep_recent = settings.max_history
    old = non_system[:-keep_recent]
    recent = non_system[-keep_recent:]

    summary = _call_llm_for_summary(old)
    if summary:
        summary_msg = {
            "role": "user",
            "content": f"【历史对话摘要】{summary}"
        }
        return system + [summary_msg] + recent

    # 摘要失败，直接截断
    return system + recent


def enhance_memory(messages: List[Dict]) -> List[Dict]:
    """
    增强记忆入口：
    1. 提取事实并更新用户画像
    2. 如果历史过长，生成摘要
    3. 返回处理后的消息列表
    """
    # 提取事实
    facts = extract_facts(messages)
    update_user_profile(facts)

    # 摘要压缩
    if should_summarize(messages):
        logger.info("对话历史过长，生成摘要...")
        messages = summarize_old_messages(messages)

    return messages
