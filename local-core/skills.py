import os
import re
import datetime
import random
import subprocess
import requests
from typing import Optional
from pathlib import Path

from logger import logger
from cache import cached


@cached(ttl=600)
def get_weather(city: str = "北京") -> str:
    """查询指定城市天气"""
    url = f"https://wttr.in/{city}?format=%C+%t+%h+%w&lang=zh"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return f"先生，{city}天气：{resp.text.strip()}"
        return "先生，天气信息获取失败。"
    except Exception:
        return "先生，天气服务暂时不可用。"


def search_file(name: str) -> str:
    """在用户目录下搜索文件"""
    results = []
    home = os.path.expanduser("~")
    try:
        for root, dirs, files in os.walk(home):
            for file in files:
                if name.lower() in file.lower():
                    results.append(os.path.join(root, file))
                if len(results) >= 5:
                    break
            if len(results) >= 5:
                break
    except PermissionError:
        pass

    if results:
        return "先生，找到以下文件：" + "；".join(results[:5])
    return "先生，未找到相关文件。"


def get_time() -> str:
    """获取当前时间"""
    now = datetime.datetime.now()
    return f"先生，现在是 {now.strftime('%Y年%m月%d日 %H点%M分')}。"


def _parse_chinese_time(time_str: str) -> Optional[datetime.datetime]:
    """简单解析中文时间，例如：明天上午10点、今天下午3点、20:00"""
    now = datetime.datetime.now()
    text = time_str.strip()

    # 日期
    date_offset = 0
    if "后天" in text:
        date_offset = 2
        text = text.replace("后天", "")
    elif "明天" in text:
        date_offset = 1
        text = text.replace("明天", "")
    elif "今天" in text:
        text = text.replace("今天", "")

    target_date = now.date() + datetime.timedelta(days=date_offset)
    hour = None
    minute = 0

    # 上午/早上/早晨 X点
    m = re.search(r"(?:上午|早上|早晨)(\d{1,2})点(?:(\d{1,2})分)?", text)
    if m:
        hour = int(m.group(1))
        if m.group(2):
            minute = int(m.group(2))

    # 下午 X点
    m = re.search(r"下午(\d{1,2})点(?:(\d{1,2})分)?", text)
    if m:
        hour = int(m.group(1)) + 12
        if m.group(2):
            minute = int(m.group(2))

    # 晚上 X点
    m = re.search(r"晚上(\d{1,2})点(?:(\d{1,2})分)?", text)
    if m:
        h = int(m.group(1))
        hour = h + 12 if h < 12 else h
        if m.group(2):
            minute = int(m.group(2))

    # X点（默认按当天，未指定上下午则保持原数字）
    if hour is None:
        m = re.search(r"(\d{1,2})点(?:(\d{1,2})分)?", text)
        if m:
            hour = int(m.group(1))
            if m.group(2):
                minute = int(m.group(2))

    # HH:MM
    if hour is None:
        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2))

    if hour is None:
        return None

    try:
        target_time = datetime.time(hour, minute)
        return datetime.datetime.combine(target_date, target_time)
    except ValueError:
        return None


def set_reminder(task: str, time_str: str) -> str:
    """设置提醒，支持中文时间解析"""
    try:
        from scheduler import add_one_time_reminder

        trigger_time = _parse_chinese_time(time_str)
        if trigger_time:
            return f"先生，{add_one_time_reminder(task, trigger_time)}"

        # 解析失败时保存为文本备忘
        os.makedirs("data", exist_ok=True)
        with open("data/reminders.txt", "a", encoding="utf-8") as f:
            f.write(f"{time_str} - {task}\n")
        return f"先生，我无法精确解析 {time_str}，已先记录到备忘，请用更明确的时间如“明天上午10点”。"
    except Exception as e:
        logger.error(f"设置提醒失败：{e}")
        return f"先生，设置提醒失败：{e}"


def list_reminders() -> str:
    """列出所有待执行提醒"""
    try:
        from scheduler import list_active_reminders
        return list_active_reminders()
    except Exception as e:
        return f"先生，读取提醒失败：{e}"


def cancel_reminder(reminder_id: int) -> str:
    """取消提醒"""
    try:
        from scheduler import cancel_reminder
        return cancel_reminder(reminder_id)
    except Exception as e:
        return f"先生，取消提醒失败：{e}"


def open_application(name: str) -> str:
    """打开常见 Windows 应用程序"""
    app_map = {
        "记事本": "notepad",
        "计算器": "calc",
        "浏览器": "msedge",
        "edge": "msedge",
        "chrome": "chrome",
        "火狐": "firefox",
        "vscode": "code",
        "微信": "wechat",
        "qq": "qq",
        "cmd": "cmd",
        "终端": "cmd",
        "画图": "mspaint",
    }
    cmd = app_map.get(name.lower(), name)
    # 防止路径穿越/绝对路径
    if "/" in cmd or "\\" in cmd or cmd.startswith("."):
        return f"先生，不允许的应用名称：{name}。"
    try:
        subprocess.Popen([cmd], shell=False)
        return f"先生，已为您打开 {name}。"
    except Exception as e:
        return f"先生，打开 {name} 失败：{e}"


@cached(ttl=30)
def get_system_info() -> str:
    """获取 CPU、内存、磁盘状态"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (
            f"先生，系统状态："
            f"CPU 使用率 {cpu:.1f}%；"
            f"内存使用 {mem.percent:.1f}%（{mem.used // 1024 // 1024}MB / {mem.total // 1024 // 1024}MB）；"
            f"C 盘已用 {disk.percent:.1f}%。"
        )
    except Exception as e:
        return f"先生，获取系统信息失败：{e}"


def write_note(title: str, content: str) -> str:
    """写入笔记到 data/notes.md"""
    os.makedirs("data", exist_ok=True)
    with open("data/notes.md", "a", encoding="utf-8") as f:
        f.write(f"## {title}\n{content}\n\n")
    return f"先生，已记录笔记《{title}》。"


def read_notes() -> str:
    """读取最近笔记"""
    path = "data/notes.md"
    if not os.path.exists(path):
        return "先生，暂时没有笔记。"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return "先生，暂时没有笔记。"
    preview = content[-500:] if len(content) > 500 else content
    return f"先生，您的最近笔记：\n{preview}"


_JOKES = [
    "先生，为什么程序员分不清圣诞节和万圣节？因为 Oct 31 == Dec 25。",
    "先生，程序员买肉夹馍：要肥瘦相间的。老板：行，横切还是竖切？程序员：按索引切。",
    "先生，一个 SQL 语句走进酒吧，走到两张桌子中间问：'我可以 join 你们吗？'",
    "先生，程序员最讨厌的四件事：1. 写注释 2. 写文档 3. 别人不写注释 4. 别人不写文档。",
]


def tell_joke() -> str:
    """讲一个冷笑话"""
    return random.choice(_JOKES)


def list_ha_entities(domain: str = "") -> str:
    """列出 Home Assistant 设备"""
    from home_assistant import list_entities
    return list_entities(domain or None)


def control_ha_device(entity_id: str, action: str) -> str:
    """控制 Home Assistant 设备"""
    from home_assistant import control_device
    return control_device(entity_id, action)


def get_ha_entity_state(entity_id: str) -> str:
    """获取 Home Assistant 实体当前状态"""
    from home_assistant import get_entity_state
    return get_entity_state(entity_id)


def list_ha_scenes() -> str:
    """列出 Home Assistant 场景"""
    from home_assistant import list_scenes
    return list_scenes()


def activate_ha_scene(scene_id: str) -> str:
    """激活 Home Assistant 场景"""
    from home_assistant import activate_scene
    return activate_scene(scene_id)


def list_ha_areas() -> str:
    """列出 Home Assistant 区域"""
    from home_assistant import list_areas
    return list_areas()


def get_ha_sensor(sensor_id: str) -> str:
    """读取 Home Assistant 传感器数值"""
    from home_assistant import get_sensor_value
    return get_sensor_value(sensor_id)


def read_emails(count: int = 5) -> str:
    """读取最近邮件"""
    from email_calendar import read_emails as _read
    return _read(count)


def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件"""
    from email_calendar import send_email as _send
    return _send(to, subject, body)


def add_event(title: str, time_str: str, description: str = "") -> str:
    """添加日程"""
    from email_calendar import add_event as _add
    return _add(title, time_str, description)


def list_events(days: int = 7) -> str:
    """列出日程"""
    from email_calendar import list_events as _list
    return _list(days)


def read_webpage(url: str) -> str:
    """读取网页"""
    from browser_automation import read_webpage as _read
    return _read(url)


def search_web(query: str) -> str:
    """网页搜索"""
    from browser_automation import search_web as _search
    return _search(query)


def run_browser_task(task_description: str) -> str:
    """执行浏览器任务"""
    from browser_automation import run_browser_task as _run
    return _run(task_description)


def safe_eval(expression: str) -> str:
    """安全计算"""
    from code_sandbox import safe_eval as _eval
    return _eval(expression)


def execute_shell(command: str) -> str:
    """执行白名单 Shell"""
    from code_sandbox import execute_shell as _exec
    return _exec(command)


def execute_python(code: str) -> str:
    """执行 Python 代码"""
    from code_sandbox import execute_python as _exec
    return _exec(code)


def run_multi_agent_task(task_description: str) -> str:
    """多 Agent 协作执行复杂任务（规划 + 执行 + 校验）"""
    from multi_agent import run_multi_agent
    return run_multi_agent(task_description)


def control_pc(action: str, **kwargs) -> str:
    """控制电脑：窗口、键鼠、剪贴板、音量、电源等"""
    from pc_control import control_pc as _ctl
    return _ctl(action, **kwargs)


def device_command(command: str) -> str:
    """统一设备控制指令，如 pc.activate.Notepad、ha.light.living_room.on"""
    from device_hub import parse_and_execute
    return parse_and_execute(command)


def list_device_domains() -> str:
    """列出已接入的设备域"""
    from device_hub import list_domains
    return list_domains()


def mqtt_publish(topic: str, payload: str) -> str:
    """发布 MQTT 消息"""
    from mqtt_bus import publish
    publish(topic, payload)
    return f"先生，已向 {topic} 发布消息。"


def add_automation_rule(rule_json: str) -> str:
    """添加自动化规则（接受 JSON 字符串）"""
    try:
        import json
        rule = json.loads(rule_json)
        from automation_engine import add_rule
        return f"先生，{add_rule(rule)}"
    except Exception as e:
        return f"先生，添加规则失败：{e}"


def list_automation_rules() -> str:
    """列出自动化规则"""
    from automation_engine import list_rules
    return list_rules()


# ---------------------------------------------------------------------------
# 视觉技能
# ---------------------------------------------------------------------------

def vision_check() -> str:
    """查看摄像头前有什么"""
    from vision import vision_summary
    return vision_summary()


def vision_snapshot() -> str:
    """拍一张照片并保存"""
    from vision import capture_snapshot
    path = capture_snapshot()
    if path:
        return f"先生，已拍照保存到：{path}"
    return "先生，拍照失败。"


# ---------------------------------------------------------------------------
# 自托管服务技能
# ---------------------------------------------------------------------------

def search_docs(query: str) -> str:
    """在 Paperless 中搜索文档"""
    from selfhost import search_documents
    return search_documents(query)


def upload_doc(file_path: str, title: str = "") -> str:
    """上传文档到 Paperless"""
    from selfhost import upload_document
    return upload_document(file_path, title or None)


def search_photos(query: str) -> str:
    """在 Immich 中搜索照片"""
    from selfhost import search_photos
    return search_photos(query)


def memory_lane() -> str:
    """获取历史上的今天照片回忆"""
    from selfhost import get_memory_lane
    return get_memory_lane()


def upload_photo(file_path: str) -> str:
    """上传照片到 Immich"""
    from selfhost import upload_photo
    return upload_photo(file_path)


def list_workflows() -> str:
    """列出 n8n 工作流"""
    from selfhost import list_workflows
    return list_workflows()


def trigger_workflow(webhook_id: str, payload: str = "") -> str:
    """触发 n8n 工作流（通过 webhook）"""
    from selfhost import trigger_webhook
    import json as _json
    try:
        data = _json.loads(payload) if payload else None
    except Exception:
        data = None
    return trigger_webhook(webhook_id, data)


def selfhost_status() -> str:
    """查看自托管服务状态"""
    from selfhost import selfhost_status
    return selfhost_status()


# ---------------------------------------------------------------------------
# 超级Agent技能（任务规划+多工具调用+代码生成）
# ---------------------------------------------------------------------------

def super_agent_task(task_description: str) -> str:
    """
    超级Agent执行复杂任务：
    自动规划步骤、调用多个工具、生成代码、处理文件、数据分析等。
    适合：写代码、数据分析、项目搭建、文件批量处理等复杂需求。
    """
    try:
        from super_agent import get_super_agent
        agent = get_super_agent()
        result = agent.execute(task_description)
        return f"先生，超级Agent已完成任务。\n{result}"
    except Exception as e:
        return f"先生，超级Agent执行失败：{e}"


def agent_chat(message: str) -> str:
    """与带工具调用能力的Agent对话（ReAct模式）"""
    try:
        from super_agent import get_super_agent
        agent = get_super_agent()
        result = agent.chat_with_tools(message)
        return result
    except Exception as e:
        return f"先生，Agent对话失败：{e}"


def write_code(project_name: str, description: str, language: str = "python") -> str:
    """
    生成代码项目：根据描述生成完整的代码文件。
    project_name: 项目/文件名
    description: 功能描述
    language: 编程语言（python/html/javascript等）
    """
    try:
        from super_agent import get_super_agent, get_tool_registry
        registry = get_tool_registry()

        from brain import get_ai_response
        prompt = f"""
请用{language}编写一个项目，项目名：{project_name}
功能描述：{description}

请生成完整的代码，并给出保存路径建议。
请直接输出代码内容，不要多余解释。
"""
        code = get_ai_response(prompt, use_mock=False)

        safe_name = re.sub(r'[^\w\-\.]', '_', project_name)
        ext = {
            "python": ".py",
            "javascript": ".js",
            "html": ".html",
            "css": ".css",
            "java": ".java",
            "cpp": ".cpp",
            "go": ".go",
        }.get(language.lower(), ".txt")

        output_dir = Path("generated_code")
        output_dir.mkdir(exist_ok=True)
        file_path = output_dir / f"{safe_name}{ext}"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        return f"先生，代码已生成并保存到：{file_path.absolute()}\n\n代码预览：\n{code[:500]}{'...' if len(code) > 500 else ''}"
    except Exception as e:
        return f"先生，代码生成失败：{e}"


def local_llm_status() -> str:
    """查看本地LLM推理引擎状态和可用模型"""
    try:
        from local_llm import get_local_llm
        llm = get_local_llm()
        status = llm.get_status()
        hw = status["hardware"]
        lines = [
            f"先生，本地LLM状态：",
            f"硬件：RAM {hw['ram_gb']}GB | VRAM {hw['vram_gb']}GB | CPU {hw['cpu_cores']}核",
            f"GPU：{hw['gpu_name'] or '无'}",
            f"Ollama：{'可用' if status['ollama_available'] else '未安装/未启动'}",
            f"已安装模型：{', '.join(status['installed_models']) if status['installed_models'] else '无'}",
            f"推荐模型：{', '.join(status['recommended_models'][:3])}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"先生，获取本地LLM状态失败：{e}"


# 技能注册表
SKILL_MAP = {
    "get_weather": get_weather,
    "search_file": search_file,
    "get_time": get_time,
    "set_reminder": set_reminder,
    "list_reminders": list_reminders,
    "cancel_reminder": cancel_reminder,
    "open_application": open_application,
    "get_system_info": get_system_info,
    "write_note": write_note,
    "read_notes": read_notes,
    "tell_joke": tell_joke,
    "list_ha_entities": list_ha_entities,
    "control_ha_device": control_ha_device,
    "get_ha_entity_state": get_ha_entity_state,
    "list_ha_scenes": list_ha_scenes,
    "activate_ha_scene": activate_ha_scene,
    "list_ha_areas": list_ha_areas,
    "get_ha_sensor": get_ha_sensor,
    "read_emails": read_emails,
    "send_email": send_email,
    "add_event": add_event,
    "list_events": list_events,
    "read_webpage": read_webpage,
    "search_web": search_web,
    "run_browser_task": run_browser_task,
    "safe_eval": safe_eval,
    "execute_shell": execute_shell,
    "execute_python": execute_python,
    "run_multi_agent_task": run_multi_agent_task,
    "control_pc": control_pc,
    "device_command": device_command,
    "list_device_domains": list_device_domains,
    "mqtt_publish": mqtt_publish,
    "add_automation_rule": add_automation_rule,
    "list_automation_rules": list_automation_rules,
    "vision_check": vision_check,
    "vision_snapshot": vision_snapshot,
    "search_docs": search_docs,
    "upload_doc": upload_doc,
    "search_photos": search_photos,
    "super_agent_task": super_agent_task,
    "agent_chat": agent_chat,
    "write_code": write_code,
    "local_llm_status": local_llm_status,
    "memory_lane": memory_lane,
    "upload_photo": upload_photo,
    "list_workflows": list_workflows,
    "trigger_workflow": trigger_workflow,
    "selfhost_status": selfhost_status,
}

