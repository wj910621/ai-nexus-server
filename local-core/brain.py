import json
import requests
from openai import OpenAI
from config import settings
from memory import get_memory, save_memory
from skills import SKILL_MAP
from knowledge_base import format_context
from memory_enhancer import enhance_memory, get_profile_summary
from logger import logger


BASE_SYSTEM_PROMPT = """你是Y·NEX，用户的私人AI管家。
- 称呼用户为“先生”。
- 回答精炼、专业，带一丝英式冷幽默。
- 你可以调用工具来帮用户完成任务，系统会自动处理工具调用。
- 请根据工具返回结果，用自然语言向先生汇报。
- 记住用户的偏好和之前说过的重要信息。
- 如果提供了【相关知识】，请优先根据知识内容回答。"""


def build_system_prompt() -> str:
    """组合基础提示词、用户画像、相关知识"""
    parts = [BASE_SYSTEM_PROMPT]

    profile = get_profile_summary()
    if profile:
        parts.append(profile)

    return "\n\n".join(parts)


# 工具定义（OpenAI / DeepSeek Function Calling 格式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，例如：北京"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_file",
            "description": "在用户目录下搜索文件名包含关键词的文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "文件名关键词"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前时间",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "设置一个提醒事项",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "提醒内容"},
                    "time_str": {"type": "string", "description": "提醒时间，如明天上午9点"}
                },
                "required": ["task", "time_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "列出所有待执行的提醒",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": "取消指定 ID 的提醒",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "integer", "description": "提醒 ID"}
                },
                "required": ["reminder_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "打开指定的 Windows 应用程序",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "应用名称，如记事本、计算器、浏览器、vscode"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "获取 CPU、内存、磁盘等系统状态",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_note",
            "description": "记录一条笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                    "content": {"type": "string", "description": "笔记内容"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_notes",
            "description": "读取最近笔记",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tell_joke",
            "description": "讲一个冷笑话",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_ha_entities",
            "description": "列出 Home Assistant 智能家居设备",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "设备类型，如 light/switch/climate/cover，留空则列出全部"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_ha_device",
            "description": "控制 Home Assistant 智能家居设备",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "设备实体 ID，如 light.living_room"},
                    "action": {"type": "string", "description": "动作：on/off/toggle/brightness/temperature/open/close/stop"}
                },
                "required": ["entity_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ha_entity_state",
            "description": "获取 Home Assistant 指定实体的当前状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "设备实体 ID，如 sensor.living_room_temperature"}
                },
                "required": ["entity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_ha_scenes",
            "description": "列出 Home Assistant 中可用的场景",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activate_ha_scene",
            "description": "激活 Home Assistant 场景",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "string", "description": "场景 ID，如 scene.movie_mode 或 movie_mode"}
                },
                "required": ["scene_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_ha_areas",
            "description": "列出 Home Assistant 中的区域（房间）",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ha_sensor",
            "description": "读取 Home Assistant 传感器数值",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {"type": "string", "description": "传感器 ID，如 living_room_temperature 或 sensor.living_room_temperature"}
                },
                "required": ["sensor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_emails",
            "description": "读取最近邮件",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "读取邮件数量，默认5"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "发送邮件",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "收件人邮箱"},
                    "subject": {"type": "string", "description": "主题"},
                    "body": {"type": "string", "description": "正文"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_event",
            "description": "添加日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "日程标题"},
                    "time_str": {"type": "string", "description": "时间，如明天下午3点"},
                    "description": {"type": "string", "description": "备注"}
                },
                "required": ["title", "time_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "列出未来日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "查看未来几天，默认7"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "读取指定网页内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页 URL"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索网页",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_browser_task",
            "description": "执行浏览器自动化任务（搜索、打开网页等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {"type": "string", "description": "任务描述，如搜索某某资料"}
                },
                "required": ["task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "safe_eval",
            "description": "安全计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 1+2*3 或 sqrt(16)"}
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "执行白名单 Shell 命令（仅只读命令）",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "命令，如 dir、python --version"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "执行受限 Python 代码片段",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python 代码，不能包含 import/open/os 等"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_multi_agent_task",
            "description": "多 Agent 协作执行复杂任务（规划 + 执行 + 校验）。适用于需要多个步骤配合的指令，如晨间日报、离家巡检、工作准备等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {"type": "string", "description": "任务描述，如\"帮我准备今天的晨间日报\""}
                },
                "required": ["task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_pc",
            "description": "控制 Windows 电脑：窗口、键鼠、剪贴板、音量、电源等",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "动作：list_windows, activate, minimize, maximize, close, type, press, click, screenshot, clipboard_get, clipboard_set, volume, mute, unmute, lock, shutdown, restart, sleep"},
                    "name": {"type": "string", "description": "窗口/进程名"},
                    "text": {"type": "string", "description": "输入文本或剪贴板内容"},
                    "keys": {"type": "string", "description": "按键组合，如 ctrl+c"},
                    "level": {"type": "integer", "description": "音量 0-100"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "device_command",
            "description": "统一设备控制指令，支持 pc/ha/phone/browser/media 等域。例如 pc.activate.Notepad、ha.light.living_room.on、pc.volume.30",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "设备指令，如 pc.activate.Notepad"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_device_domains",
            "description": "列出已接入的设备控制域",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mqtt_publish",
            "description": "向 MQTT 主题发布消息，供手机/传感器订阅",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "MQTT 主题"},
                    "payload": {"type": "string", "description": "消息内容"}
                },
                "required": ["topic", "payload"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_automation_rule",
            "description": "添加一条自动化规则（触发器-条件-动作）。参数为 JSON 字符串。",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_json": {"type": "string", "description": "规则 JSON 字符串"}
                },
                "required": ["rule_json"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_automation_rules",
            "description": "列出当前所有自动化规则",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_check",
            "description": "查看摄像头前有什么（人脸、姿态、运动检测）",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_snapshot",
            "description": "用摄像头拍一张照片并保存",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "在 Paperless-ngx 文档管理系统中搜索文档",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_photos",
            "description": "在 Immich 相册中搜索照片",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如 海边、生日、猫"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_lane",
            "description": "查看 Immich 历史上的今天照片回忆",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_workflows",
            "description": "列出 n8n 工作流",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_workflow",
            "description": "通过 webhook 触发 n8n 工作流",
            "parameters": {
                "type": "object",
                "properties": {
                    "webhook_id": {"type": "string", "description": "工作流 webhook ID 或完整 URL"},
                    "payload": {"type": "string", "description": "JSON 格式的负载数据，可选"}
                },
                "required": ["webhook_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "selfhost_status",
            "description": "查看所有自托管服务（Paperless/Immich/n8n）的连接状态",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "super_agent_task",
            "description": "超级Agent执行复杂任务：自动规划步骤、调用多个工具、处理复杂需求。适合：写代码、数据分析、项目搭建、文件批量处理等需要多步操作的任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {"type": "string", "description": "详细的任务描述，越详细越好"}
                },
                "required": ["task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_code",
            "description": "生成代码项目：根据功能描述生成完整的代码文件并保存",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "项目或文件名称"},
                    "description": {"type": "string", "description": "详细的功能描述"},
                    "language": {"type": "string", "description": "编程语言，如python/html/javascript/java等"}
                },
                "required": ["project_name", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "local_llm_status",
            "description": "查看本地LLM推理引擎状态、硬件配置、已安装模型和推荐模型",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]


def _call_ollama(messages):
    """调用本地 Ollama 模型"""
    url = f"{settings.local_base_url}/api/chat"
    payload = {
        "model": settings.local_model,
        "messages": messages,
        "stream": False,
        "tools": TOOLS
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["message"]
    except Exception as e:
        logger.error(f"本地模型调用失败：{e}")
        return {"content": f"本地模型调用失败：{e}"}


def validate_api_key():
    """校验 DeepSeek API Key 是否有效（发起一个简单请求）"""
    if not settings.deepseek_api_key:
        return False, "未配置 DEEPSEEK_API_KEY"

    if not settings.deepseek_api_key.startswith("sk-"):
        return False, "API Key 格式不正确，应以 sk- 开头"

    try:
        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )
        # 发一个 cheapest 的请求验证连通性
        resp = client.chat.completions.create(
            model=settings.online_model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5
        )
        return True, f"验证通过，可用余额或额度请登录平台查看"
    except Exception as e:
        return False, f"API Key 验证失败：{e}"


def _call_deepseek(messages):
    """调用 DeepSeek 在线 API，失败时返回包含错误信息的字典"""
    if not settings.deepseek_api_key:
        return {"content": "DeepSeek API Key 未配置。"}

    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url
    )

    # 简单重试机制
    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=settings.online_model,
                messages=messages,
                tools=TOOLS,
                temperature=0.7,
                timeout=60
            )
            return response.choices[0].message
        except Exception as e:
            last_error = e
            logger.warning(f"DeepSeek API 调用尝试 {attempt + 1} 失败：{e}")

    logger.error(f"DeepSeek API 调用失败：{last_error}")
    return {"content": f"DeepSeek API 调用失败：{last_error}"}


def _normalize_tool_call(tc):
    """统一工具调用格式（兼容 OpenAI 对象与 Ollama 字典）"""
    if isinstance(tc, dict):
        func = tc.get("function", {})
        return {
            "id": tc.get("id", "call_1"),
            "type": "function",
            "function": {
                "name": func.get("name", ""),
                "arguments": func.get("arguments", "{}")
            }
        }
    # OpenAI 对象风格
    func = tc.function
    return {
        "id": getattr(tc, "id", "call_1"),
        "type": "function",
        "function": {
            "name": func.name,
            "arguments": func.arguments
        }
    }


def _execute_tool(tool_call):
    """执行单个工具调用"""
    name = tool_call["function"]["name"]
    raw_args = tool_call["function"]["arguments"]

    # 兼容字符串 JSON（OpenAI/DeepSeek）和已解析字典（Ollama）
    if isinstance(raw_args, str):
        args = json.loads(raw_args)
    else:
        args = raw_args

    if name in SKILL_MAP:
        return SKILL_MAP[name](**args)
    return f"先生，未知工具：{name}"


def _mock_chat(messages, is_summary=False):
    """Mock LLM：根据用户输入关键词模拟工具调用或直接回复
    用于无 API Key 时测试工具调用链。
    """
    import re
    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "")
            break

    # 如果是总结工具结果，直接返回技能函数的结果
    # 技能函数已自带完整回复（含"先生，"），不额外拼前缀
    if is_summary:
        for m in reversed(messages):
            if m.get("role") == "tool":
                return m.get("content", "")
        return "先生，已为您处理。"

    text = user_text.lower()

    # 模拟工具调用
    if "天气" in text or "气温" in text:
        city = "北京"
        for c in ["北京", "上海", "广州", "深圳", "杭州", "成都"]:
            if c in user_text:
                city = c
                break
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_1",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"city": city})
                }
            }]
        }

    if "时间" in text or "几点" in text:
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_2",
                "function": {
                    "name": "get_time",
                    "arguments": "{}"
                }
            }]
        }

    file_keywords = ["简历", "合同", "报告", "图片", "文档", "文件"]
    if "找文件" in text or "文件" in text or ("搜索" in text and any(kw in text for kw in file_keywords)):
        keyword = "简历"
        for kw in file_keywords:
            if kw in user_text:
                keyword = kw
                break
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_3",
                "function": {
                    "name": "search_file",
                    "arguments": json.dumps({"name": keyword})
                }
            }]
        }

    if "提醒" in text or "记得" in text:
        # 取消提醒
        if "取消" in text:
            reminder_id = 1
            m = re.search(r"取消.*?提醒.*?[(\[](\d+)[)\]]", user_text)
            if not m:
                m = re.search(r"取消提醒\s*(\d+)", user_text)
            if m:
                reminder_id = int(m.group(1))
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_4a",
                    "function": {
                        "name": "cancel_reminder",
                        "arguments": json.dumps({"reminder_id": reminder_id})
                    }
                }]
            }

        # 列出提醒
        if "列出" in text or "查看" in text or "有什么" in text or "哪些" in text:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_4b",
                    "function": {
                        "name": "list_reminders",
                        "arguments": "{}"
                    }
                }]
            }

        # 设置提醒
        task = "您交代的事项"
        time_str = "稍后"
        ts = r'(?:今[天晚]|明[天早]|后[天早])(?:[上午下午晚早]+\d*[点时：:]\d*分?)?|\d+[点时：:]\d*分?'
        m_a = re.search(r'(?:提醒|记得).*?我?\s*(' + ts + r')\s*(.+)', user_text)
        m_b = re.search(r'(?:提醒|记得).*?我?\s*(.+?)\s*(?:在|于)?\s*(' + ts + r')\s*$', user_text)
        if m_a:
            time_str = m_a.group(1).strip()
            task = m_a.group(2).strip()
        elif m_b:
            time_str = m_b.group(2).strip()
            task = m_b.group(1).strip()
        else:
            rest = re.sub(r'^(?:提醒|记得).*?我?\s*', '', user_text)
            if rest:
                task = rest
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_4",
                "function": {
                    "name": "set_reminder",
                    "arguments": json.dumps({"task": task, "time_str": time_str})
                }
            }]
        }

    if "打开" in text or "启动" in text:
        # 避免把智能家居/网页指令误判为开应用
        if any(k in text for k in ["灯", "空调", "窗帘", "客厅", "卧室", "厨房"]):
            pass
        elif "http" in user_text or ".com" in user_text or "www." in user_text:
            pass
        else:
            name = "记事本"
            for app in ["记事本", "计算器", "浏览器", "vscode", "chrome", "edge", "cmd", "画图"]:
                if app in user_text.lower():
                    name = app
                    break
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_5",
                    "function": {
                        "name": "open_application",
                        "arguments": json.dumps({"name": name})
                    }
                }]
            }

    if "系统" in text or "cpu" in text or "内存" in text or "磁盘" in text:
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_6",
                "function": {
                    "name": "get_system_info",
                    "arguments": "{}"
                }
            }]
        }

    if "写笔记" in text or "记录" in text or "记一下" in text:
        # 简单提取："写笔记 标题 内容" 或 "记录一下 内容"
        rest = re.sub(r'^(?:写笔记|记录|记一下)\s*', '', user_text).strip()
        title = rest[:20] if rest else "未命名"
        content = rest if rest else "无内容"
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_7",
                "function": {
                    "name": "write_note",
                    "arguments": json.dumps({"title": title, "content": content})
                }
            }]
        }

    if "看笔记" in text or "读笔记" in text or "我的笔记" in text:
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_8",
                "function": {
                    "name": "read_notes",
                    "arguments": "{}"
                }
            }]
        }

    if "笑话" in text or "幽默" in text or "无聊" in text:
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_9",
                "function": {
                    "name": "tell_joke",
                    "arguments": "{}"
                }
            }]
        }

    if any(k in text for k in ["有哪些设备", "设备域", "接入设备"]):
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_24",
                "function": {
                    "name": "list_device_domains",
                    "arguments": "{}"
                }
            }]
        }

    if any(k in text for k in ["智能家居", "设备", "灯", "空调", "窗帘", "场景", "区域", "房间", "传感器", "温度", "湿度", "亮度"]):
        # 场景
        if "场景" in text:
            if any(w in text for w in ["激活", "打开", "启用", "执行"]):
                scene_id = "movie_mode"
                m = re.search(r"[\"\']([^\"\']+)[\"\']", user_text)
                if m:
                    scene_id = m.group(1)
                else:
                    m = re.search(r"(?:场景|scene)[.\s]*([a-zA-Z0-9_\u4e00-\u9fa5]+)", user_text)
                    if m:
                        scene_id = m.group(1)
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": "mock_10a",
                        "function": {
                            "name": "activate_ha_scene",
                            "arguments": json.dumps({"scene_id": scene_id})
                        }
                    }]
                }
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_10b",
                    "function": {
                        "name": "list_ha_scenes",
                        "arguments": "{}"
                    }
                }]
            }

        # 区域/房间
        if "区域" in text or "房间" in text or "area" in text:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_10c",
                    "function": {
                        "name": "list_ha_areas",
                        "arguments": "{}"
                    }
                }]
            }

        # 传感器 / 状态 / 温度 / 湿度
        if any(k in text for k in ["传感器", "温度", "湿度", "状态", "亮度", "多少", "读数"]):
            entity_id = "sensor.living_room_temperature"
            m = re.search(r"[\"\']([^\"\']+)[\"\']", user_text)
            if m:
                entity_id = m.group(1)
            else:
                m = re.search(r"(?:传感器|sensor|状态|state)[.\s]*([a-zA-Z0-9_\u4e00-\u9fa5]+)", user_text)
                if m:
                    captured = m.group(1)
                    # 过滤掉纯疑问词，保留看起来像 ID 的片段
                    if captured and not all(c in "多少度怎么样状态" for c in captured):
                        entity_id = captured
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_10d",
                    "function": {
                        "name": "get_ha_sensor",
                        "arguments": json.dumps({"sensor_id": entity_id})
                    }
                }]
            }

        # 控制设备
        if any(word in text for word in ["打开", "关闭", "开", "关", "调亮", "调暗"]):
            action = "toggle"
            if any(w in text for w in ["打开", "开"]):
                action = "on"
            elif any(w in text for w in ["关闭", "关"]):
                action = "off"

            entity_id = "light.living_room"
            if "客厅" in text:
                entity_id = "light.living_room"
            elif "卧室" in text:
                entity_id = "light.bedroom"
            elif "厨房" in text:
                entity_id = "light.kitchen"

            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_10",
                    "function": {
                        "name": "control_ha_device",
                        "arguments": json.dumps({"entity_id": entity_id, "action": action})
                    }
                }]
            }

        # 列出设备
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_11",
                "function": {
                    "name": "list_ha_entities",
                    "arguments": json.dumps({"domain": "light"})
                }
            }]
        }

    if "邮件" in text or "邮箱" in text or "email" in text:
        if any(w in text for w in ["发", "发送", "写", "回复"]):
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_12",
                    "function": {
                        "name": "send_email",
                        "arguments": json.dumps({
                            "to": "example@example.com",
                            "subject": "主题",
                            "body": "先生，请补充收件人和内容。"
                        })
                    }
                }]
            }
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_13",
                "function": {
                    "name": "read_emails",
                    "arguments": json.dumps({"count": 5})
                }
            }]
        }

    if "日程" in text or "会议" in text or "约会" in text or "安排" in text:
        if any(w in text for w in ["添加", "新建", "增加", "记"]) and ("点" in text or "天" in text):
            title = "新日程"
            time_str = "明天上午10点"
            m = re.search(r"(?:添加|新建|增加|记)\s*(.+?)(?:在|于|，|明天|今天|后天|上午|下午|晚上)", user_text)
            if m:
                title = m.group(1).strip()
            m_time = re.search(r"(明天|今天|后天|上午\d+点|下午\d+点|晚上\d+点|\d+:\d+)", user_text)
            if m_time:
                time_str = m_time.group(1)
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_14",
                    "function": {
                        "name": "add_event",
                        "arguments": json.dumps({"title": title, "time_str": time_str})
                    }
                }]
            }
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_15",
                "function": {
                    "name": "list_events",
                    "arguments": json.dumps({"days": 7})
                }
            }]
        }

    if "网页" in text or "搜索" in text or "查资料" in text or "打开网站" in text or re.search(r"https?://\S+|\S+\.com|\S+\.cn|\S+\.net", user_text):
        if "http" in user_text or "www." in user_text or ".com" in user_text or ".cn" in user_text or ".net" in user_text:
            m = re.search(r"https?://\S+|www\.\S+|\S+\.com|\S+\.cn|\S+\.net", user_text)
            url = m.group(0) if m else "example.com"
            if not url.startswith("http"):
                url = "https://" + url
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_16",
                    "function": {
                        "name": "read_webpage",
                        "arguments": json.dumps({"url": url})
                    }
                }]
            }
        # 提取搜索关键词
        query = user_text
        for prefix in ["搜索", "查一下", "查资料", "帮我搜"]:
            query = query.replace(prefix, "")
        query = query.strip(" 。，？")
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_17",
                "function": {
                    "name": "search_web",
                    "arguments": json.dumps({"query": query or "最新新闻"})
                }
            }]
        }

    if "计算" in text or "等于" in text or "算一下" in text or re.search(r"\d+\s*[+\-*/]\s*\d+", user_text):
        expr = user_text
        for prefix in ["计算", "算一下", "等于"]:
            expr = expr.replace(prefix, "")
        expr = expr.strip(" 。，？")
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_18",
                "function": {
                    "name": "safe_eval",
                    "arguments": json.dumps({"expression": expr or "1+1"})
                }
            }]
        }

    if "执行代码" in text or "运行 python" in text or "写段代码" in text:
        code = re.sub(r".*?(?:执行代码|运行 python|写段代码)[:：]?\s*", "", user_text).strip()
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_19",
                "function": {
                    "name": "execute_python",
                    "arguments": json.dumps({"code": code or "print('hello')"})
                }
            }]
        }

    if "执行命令" in text or "运行命令" in text:
        cmd = re.sub(r".*?(?:执行命令|运行命令)[:：]?\s*", "", user_text).strip()
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_20",
                "function": {
                    "name": "execute_shell",
                    "arguments": json.dumps({"command": cmd or "python --version"})
                }
            }]
        }

    if any(k in text for k in ["多 agent", "多 agent", "协作", "晨间日报", "离家巡检", "工作准备", "准备今天", "帮我检查"]):
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_21",
                "function": {
                    "name": "run_multi_agent_task",
                    "arguments": json.dumps({"task_description": user_text})
                }
            }]
        }

    # 电脑控制相关
    if any(k in text for k in ["锁屏", "关机", "重启", "音量", "静音", "截图", "剪贴板"]):
        action = ""
        kwargs = {}
        if "锁屏" in text:
            action = "lock"
        elif "关机" in text:
            action = "shutdown"
        elif "重启" in text:
            action = "restart"
        elif "截图" in text:
            action = "screenshot"
        elif "剪贴板" in text and ("读" in text or "看" in text):
            action = "clipboard_get"
        elif "剪贴板" in text:
            action = "clipboard_set"
            kwargs = {"text": user_text.replace("剪贴板", "").strip(" 。：，")}
        elif "静音" in text or "取消静音" in text:
            action = "unmute" if "取消" in text else "mute"
        elif "音量" in text:
            action = "volume"
            m = re.search(r"(\d+)", user_text)
            kwargs = {"level": int(m.group(1)) if m else 50}

        if action:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "mock_22",
                    "function": {
                        "name": "control_pc",
                        "arguments": json.dumps({"action": action, **kwargs})
                    }
                }]
            }

    # 设备统一控制（协议格式或自然语言）
    if re.match(r"^(pc|ha|phone|browser|media)\.", user_text):
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_23",
                "function": {
                    "name": "device_command",
                    "arguments": json.dumps({"command": user_text})
                }
            }]
        }

    if "规则" in text and ("列出" in text or "查看" in text or "有哪些" in text):
        return {
            "content": "",
            "tool_calls": [{
                "id": "mock_25",
                "function": {
                    "name": "list_automation_rules",
                    "arguments": "{}"
                }
            }]
        }

    # 默认直接回复
    return {"content": "先生，我已收到您的指令。"}


def get_ai_response(user_text: str, use_mock: bool = False) -> str:
    """获取 AI 回复，支持工具调用、RAG 知识检索与记忆增强
    
    Args:
        user_text: 用户输入文本
        use_mock: 是否使用 Mock LLM（无 API Key 时测试用）
    """
    messages = get_memory()

    # 增强记忆：提取事实、更新画像、摘要压缩
    messages = enhance_memory(messages)

    # 确保系统提示存在且最新
    system_prompt = build_system_prompt()
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})
    else:
        messages[0]["content"] = system_prompt

    # 检索长期知识并拼接到用户输入
    knowledge = format_context(user_text)
    if knowledge:
        user_content = f"{knowledge}\n\n【用户问题】\n{user_text}"
    else:
        user_content = user_text

    messages.append({"role": "user", "content": user_content})

    # 第一步：选择模型并调用
    if use_mock:
        msg = _mock_chat(messages)
    else:
        msg = None
        if settings.use_local_first:
            msg = _call_ollama(messages)
            if msg.get("content", "").startswith("本地模型调用失败"):
                msg = None

        if msg is None and settings.deepseek_api_key:
            msg = _call_deepseek(messages)

        if msg is None:
            return "先生，请配置 DeepSeek API Key 或启动 Ollama 本地模型。"

    # 第二步：处理工具调用
    if isinstance(msg, dict):
        tool_calls = msg.get("tool_calls")
        content = msg.get("content", "")
    else:
        tool_calls = getattr(msg, "tool_calls", None)
        content = getattr(msg, "content", "")

    if tool_calls:
        assistant_msg = {
            "role": "assistant",
            "content": content,
            "tool_calls": [_normalize_tool_call(tc) for tc in tool_calls]
        }
        messages.append(assistant_msg)

        for tc in assistant_msg["tool_calls"]:
            logger.info(f"执行工具：{tc['function']['name']}，参数：{tc['function']['arguments']}")
            result = _execute_tool(tc)
            logger.debug(f"工具结果：{result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })

        # 第三步：让模型总结工具结果
        if use_mock:
            reply = _mock_chat(messages, is_summary=True)
        elif settings.use_local_first:
            final = _call_ollama(messages)
            reply = final.get("content", "") if isinstance(final, dict) else getattr(final, "content", "")
        else:
            final = _call_deepseek(messages)
            reply = final.get("content", "") if isinstance(final, dict) else getattr(final, "content", "")
    else:
        reply = content

    messages.append({"role": "assistant", "content": reply})
    save_memory(messages)
    return reply
