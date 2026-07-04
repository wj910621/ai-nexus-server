"""
自动化规则引擎
触发器（trigger）-> 条件（condition）-> 动作（action）

规则示例：
{
    "id": "leaving_home",
    "name": "离家模式",
    "enabled": true,
    "trigger": {"type": "mqtt", "topic": "jarvis/phone/status", "payload_contains": "away"},
    "conditions": [{"type": "time_range", "start": "08:00", "end": "23:00"}],
    "actions": [
        {"type": "device", "command": "ha.light.all.off"},
        {"type": "device", "command": "pc.lock"},
        {"type": "notify", "message": "先生，已启动离家模式。"}
    ]
}
"""

import json
import os
import re
import threading
import time
from typing import Dict, Any, List, Optional

from logger import logger


RULES_FILE = "data/automation_rules.json"
_rules: List[Dict[str, Any]] = []
_lock = threading.Lock()
_scheduler_started = False


def _load_rules() -> List[Dict[str, Any]]:
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载规则失败：{e}")
    return []


def _save_rules():
    try:
        os.makedirs(os.path.dirname(RULES_FILE) or "data", exist_ok=True)
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(_rules, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存规则失败：{e}")


def get_rules() -> List[Dict[str, Any]]:
    global _rules
    if not _rules:
        _rules = _load_rules()
    return _rules


def add_rule(rule: Dict[str, Any]) -> str:
    """添加规则"""
    if "id" not in rule:
        rule["id"] = f"rule_{int(time.time() * 1000)}"
    get_rules()
    with _lock:
        # 去重
        _rules[:] = [r for r in _rules if r.get("id") != rule["id"]]
        _rules.append(rule)
        _save_rules()
    _subscribe_rule(rule)
    return f"已添加规则「{rule.get('name', rule['id'])}」"


def remove_rule(rule_id: str) -> str:
    get_rules()
    with _lock:
        before = len(_rules)
        _rules[:] = [r for r in _rules if r.get("id") != rule_id]
        after = len(_rules)
        _save_rules()
    if after < before:
        return f"已删除规则 {rule_id}"
    return f"未找到规则 {rule_id}"


def list_rules() -> str:
    rules = get_rules()
    if not rules:
        return "先生，当前没有自动化规则。"
    lines = ["先生，当前自动化规则："]
    for r in rules:
        status = "启用" if r.get("enabled", True) else "停用"
        lines.append(f"- [{status}] {r.get('id')}: {r.get('name', '未命名')}")
    return "\n".join(lines)


def _evaluate_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """评估单个条件"""
    ctype = condition.get("type")

    if ctype == "time_range":
        now = time.localtime()
        now_min = now.tm_hour * 60 + now.tm_min
        start = condition.get("start", "00:00")
        end = condition.get("end", "23:59")
        sm = re.match(r"(\d{1,2}):(\d{2})", start)
        em = re.match(r"(\d{1,2}):(\d{2})", end)
        if sm and em:
            start_min = int(sm.group(1)) * 60 + int(sm.group(2))
            end_min = int(em.group(1)) * 60 + int(em.group(2))
            return start_min <= now_min <= end_min
        return True

    if ctype == "sensor_present":
        try:
            from esp_sensors import is_someone_present
            return is_someone_present(condition.get("timeout", 300))
        except Exception:
            return False

    if ctype == "sensor_absent":
        try:
            from esp_sensors import is_someone_present
            return not is_someone_present(condition.get("timeout", 300))
        except Exception:
            return False

    if ctype == "payload_contains":
        payload = context.get("payload", "")
        needle = condition.get("value", "")
        return needle in str(payload)

    if ctype == "payload_equals":
        payload = context.get("payload", "")
        return str(payload) == str(condition.get("value"))

    if ctype == "state_equals":
        return context.get(condition.get("key")) == condition.get("value")

    # 未知条件默认通过
    return True


def _evaluate_conditions(rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
    for c in rule.get("conditions", []):
        if not _evaluate_condition(c, context):
            return False
    return True


def _execute_action(action: Dict[str, Any], context: Dict[str, Any]) -> str:
    atype = action.get("type")

    if atype == "device":
        from device_hub import parse_and_execute
        cmd = action.get("command", "")
        return parse_and_execute(cmd)

    if atype == "skill":
        from skills import SKILL_MAP
        name = action.get("name", "")
        args = action.get("args", {})
        if name in SKILL_MAP:
            return SKILL_MAP[name](**args)
        return f"未知技能：{name}"

    if atype == "notify":
        msg = action.get("message", "")
        try:
            from speech import speak
            speak(msg)
        except Exception:
            print(f"\nY·NEX: {msg}")
        return msg

    if atype == "mqtt_publish":
        from mqtt_bus import publish
        publish(action.get("topic", ""), action.get("payload", ""))
        return "已发布 MQTT 消息"

    return f"未知动作类型：{atype}"


def _execute_rule_actions(rule: Dict[str, Any], context: Dict[str, Any]):
    logger.info(f"触发规则：{rule.get('name', rule.get('id'))}")
    results = []
    for action in rule.get("actions", []):
        try:
            result = _execute_action(action, context)
            results.append(result)
            logger.info(f"  动作结果：{result}")
        except Exception as e:
            logger.exception(f"规则动作执行失败：{e}")
            results.append(f"失败：{e}")
    return results


def _on_mqtt_message(topic: str, payload: Any):
    context = {"topic": topic, "payload": payload, "source": "mqtt"}

    # 传感器消息上下文增强
    if topic.startswith("ynex/sensor/"):
        try:
            from esp_sensors import _parse_topic, _normalize_state
            parsed = _parse_topic(topic)
            if parsed:
                location, device_type, device_id = parsed
                data = payload if isinstance(payload, dict) else {}
                if isinstance(payload, str):
                    try:
                        import json
                        data = json.loads(payload)
                    except Exception:
                        data = {"state": payload}
                context.update({
                    "location": location,
                    "device_type": device_type,
                    "device_id": device_id,
                    "state": _normalize_state(data.get("state", ""), device_type),
                    "value": data.get("value"),
                })
        except Exception:
            pass

    for rule in get_rules():
        if not rule.get("enabled", True):
            continue
        trigger = rule.get("trigger", {})
        ttype = trigger.get("type")

        if ttype == "mqtt":
            if not _topic_match(trigger.get("topic", ""), topic):
                continue
            if "payload_contains" in trigger and trigger["payload_contains"] not in str(payload):
                continue
            if "payload_equals" in trigger and str(trigger["payload_equals"]) != str(payload):
                continue

        elif ttype == "sensor":
            if not topic.startswith("ynex/sensor/"):
                continue
            if trigger.get("device_type") and trigger.get("device_type") != context.get("device_type"):
                continue
            if trigger.get("state") and trigger.get("state") != context.get("state"):
                continue
            if trigger.get("location") and trigger.get("location") != context.get("location"):
                continue

        else:
            continue

        if _evaluate_conditions(rule, context):
            _execute_rule_actions(rule, context)


def _topic_match(subscription: str, topic: str) -> bool:
    sub_parts = subscription.split("/")
    topic_parts = topic.split("/")
    for i, part in enumerate(sub_parts):
        if part == "#":
            return True
        if i >= len(topic_parts):
            return False
        if part != "+" and part != topic_parts[i]:
            return False
    return len(sub_parts) == len(topic_parts)


def _subscribe_rule(rule: Dict[str, Any]):
    trigger = rule.get("trigger", {})
    if trigger.get("type") == "mqtt":
        from mqtt_bus import subscribe
        subscribe(trigger.get("topic", "#"), _on_mqtt_message)


def _start_time_scheduler():
    """启动基于简单轮询的时间触发器"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def loop():
        while True:
            try:
                now = time.localtime()
                context = {"source": "timer", "time": time.strftime("%H:%M", now)}
                for rule in get_rules():
                    if not rule.get("enabled", True):
                        continue
                    trigger = rule.get("trigger", {})
                    if trigger.get("type") != "time":
                        continue
                    scheduled = trigger.get("at", "")
                    if scheduled == context["time"] and now.tm_sec < 5:
                        if _evaluate_conditions(rule, context):
                            _execute_rule_actions(rule, context)
            except Exception as e:
                logger.exception(f"时间触发器异常：{e}")
            time.sleep(5)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def start_engine():
    """启动自动化引擎：加载规则并订阅"""
    rules = get_rules()
    for rule in rules:
        _subscribe_rule(rule)
    _start_time_scheduler()
    logger.info(f"自动化引擎已启动，共 {len(rules)} 条规则。")


def trigger_event(event_type: str, data: Dict[str, Any]):
    """手动触发事件，测试用"""
    context = {"source": "event", "event_type": event_type, **data}
    for rule in get_rules():
        if not rule.get("enabled", True):
            continue
        trigger = rule.get("trigger", {})
        if trigger.get("type") == "event" and trigger.get("event_type") == event_type:
            if _evaluate_conditions(rule, context):
                _execute_rule_actions(rule, context)


if __name__ == "__main__":
    add_rule({
        "id": "test",
        "name": "测试规则",
        "enabled": True,
        "trigger": {"type": "event", "event_type": "test"},
        "actions": [{"type": "notify", "message": "先生，测试规则已触发。"}]
    })
    start_engine()
    trigger_event("test", {})
    time.sleep(1)
