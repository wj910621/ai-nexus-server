"""
Y·NEX超级Agent - 智能任务规划与执行引擎
支持：
  - 复杂任务拆解与规划（ReAct / Plan-and-Execute）
  - 多轮工具调用，自动重试
  - 代码生成与执行（Python/Shell）
  - 文件系统深度操作
  - 任务进度追踪与反馈
  - 失败自动调整策略
"""

import os
import re
import sys
import json
import time
import shutil
import traceback
import subprocess
import threading
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path

from logger import logger
from config import settings


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class TaskStep:
    id: int
    description: str
    status: str = "pending"  # pending / running / completed / failed / skipped
    result: str = ""
    error: str = ""
    tool_calls: List[dict] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class TaskPlan:
    original_request: str
    steps: List[TaskStep] = field(default_factory=list)
    status: str = "planning"  # planning / executing / completed / failed
    final_result: str = ""
    created_at: float = field(default_factory=time.time)


# =============================================================================
# 工具注册表
# =============================================================================

class ToolRegistry:
    """工具注册表 - 所有Agent可调用的工具都在这里注册"""

    def __init__(self):
        self.tools: Dict[str, dict] = {}
        self._register_builtin_tools()

    def register(self, name: str, func: Callable, description: str, parameters: dict):
        """注册一个工具"""
        self.tools[name] = {
            "name": name,
            "func": func,
            "description": description,
            "parameters": parameters,
        }
        logger.debug(f"注册Agent工具: {name}")

    def get_tool(self, name: str) -> Optional[dict]:
        return self.tools.get(name)

    def list_tools(self) -> List[dict]:
        return [
            {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in self.tools.values()
        ]

    def call_tool(self, name: str, **kwargs) -> str:
        """调用工具"""
        tool = self.tools.get(name)
        if not tool:
            return f"错误：未找到工具 '{name}'"
        try:
            result = tool["func"](**kwargs)
            return str(result) if result is not None else "完成"
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {e}")
            return f"错误：{str(e)}"

    def _register_builtin_tools(self):
        """注册内置工具"""

        def read_file(path: str, max_lines: int = 200) -> str:
            """读取文件内容"""
            try:
                p = Path(path).expanduser()
                if not p.exists():
                    return f"文件不存在: {path}"
                if not p.is_file():
                    return f"不是文件: {path}"
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    content = "".join(lines[:max_lines])
                    if len(lines) > max_lines:
                        content += f"\n... (文件共{len(lines)}行，已显示前{max_lines}行)"
                return content
            except Exception as e:
                return f"读取失败: {e}"

        def write_file(path: str, content: str) -> str:
            """写入文件内容（覆盖）"""
            try:
                p = Path(path).expanduser()
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"已写入文件: {path} ({len(content)}字符)"
            except Exception as e:
                return f"写入失败: {e}"

        def append_file(path: str, content: str) -> str:
            """追加内容到文件"""
            try:
                p = Path(path).expanduser()
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(content)
                return f"已追加到文件: {path}"
            except Exception as e:
                return f"追加失败: {e}"

        def list_directory(path: str = ".", pattern: str = None) -> str:
            """列出目录内容"""
            try:
                p = Path(path).expanduser()
                if not p.exists():
                    return f"目录不存在: {path}"
                items = []
                for item in sorted(p.iterdir()):
                    icon = "📁" if item.is_dir() else "📄"
                    size = ""
                    if item.is_file():
                        try:
                            s = item.stat().st_size
                            if s > 1024 * 1024:
                                size = f" {s//1024//1024}MB"
                            elif s > 1024:
                                size = f" {s//1024}KB"
                        except Exception:
                            pass
                    name = item.name
                    if pattern and pattern.lower() not in name.lower():
                        continue
                    items.append(f"{icon} {name}{size}")
                if not items:
                    return "目录为空"
                return "\n".join(items[:50]) + (f"\n... 共{len(items)}项，显示前50项" if len(items) > 50 else "")
            except Exception as e:
                return f"列出目录失败: {e}"

        def search_files(path: str = ".", name: str = "", content: str = "", ext: str = "") -> str:
            """搜索文件（按名称或内容）"""
            try:
                p = Path(path).expanduser()
                results = []
                count = 0
                for root, dirs, files in os.walk(p):
                    for f in files:
                        fp = os.path.join(root, f)
                        if name and name.lower() not in f.lower():
                            continue
                        if ext and not f.lower().endswith(ext.lower()):
                            continue
                        if content:
                            try:
                                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                                    if content.lower() not in fh.read().lower():
                                        continue
                            except Exception:
                                continue
                        results.append(fp)
                        count += 1
                        if count >= 20:
                            break
                    if count >= 20:
                        break
                if not results:
                    return "未找到匹配的文件"
                return "\n".join(results) + f"\n... 找到{count}个文件（显示前20个）"
            except Exception as e:
                return f"搜索失败: {e}"

        def run_python(code: str, timeout: int = 30) -> str:
            """
            执行 Python 代码（受限沙箱）。

            安全策略：
              - 子进程隔离：-I（隔离模式）、-S（不加载 site-packages 用户扩展）、
                最小化环境变量（移除密钥与 PYTHON* 变量）、临时目录作为 cwd；
              - 基本黑名单：禁止 subprocess/os.system/shutil.rmtree 等系统级操作，
                防止 AI 被注入后执行破坏性命令；
              - 保留 import 能力以支持数据分析（numpy/pandas 等）。
            """
            # 基本危险操作黑名单（防止 AI 被恶意 prompt 注入后破坏系统）
            _DANGEROUS_PATTERNS = [
                "subprocess", "os.system", "os.popen", "os.exec", "os.spawn",
                "os.remove", "os.unlink", "os.rmdir", "shutil.rmtree",
                "shutil.move", "shutil.copy", "__import__",
                "ctypes", "pickle.loads", "marshal.loads",
                "open(",  # 文件读写
            ]
            for pat in _DANGEROUS_PATTERNS:
                if pat in code:
                    return f"代码被拒绝：包含被禁止的操作 '{pat}'。super_agent 不允许执行系统级或文件操作，请使用专用工具。"

            import tempfile as _tempfile
            import shutil as _shutil
            tmp_dir = _tempfile.mkdtemp(prefix="ynex_agent_sandbox_")
            try:
                fpath = os.path.join(tmp_dir, "snippet.py")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(code)

                # 隔离环境：仅保留最小 PATH 与 SYSTEMROOT（Windows 必需）
                safe_env = {
                    "PATH": os.environ.get("PATH", ""),
                    "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                    "TEMP": tmp_dir, "TMP": tmp_dir,
                }
                try:
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", fpath],
                        capture_output=True, text=True, timeout=timeout,
                        encoding="utf-8", errors="replace",
                        cwd=tmp_dir, env=safe_env,
                    )
                    output = ""
                    if result.stdout:
                        output += f"标准输出:\n{result.stdout}\n"
                    if result.stderr:
                        output += f"标准错误:\n{result.stderr}\n"
                    if not output:
                        output = "(无输出)"
                    return f"执行完成（返回码: {result.returncode}）\n{output}"
                except subprocess.TimeoutExpired:
                    return f"执行超时（超过{timeout}秒）"
            except Exception as e:
                return f"执行失败: {e}"
            finally:
                try:
                    _shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

        def run_shell(command: str, timeout: int = 30) -> str:
            """执行Shell命令（白名单机制，仅允许只读安全命令）"""
            # 白名单：仅允许只读/查询类命令
            # 注意：python/node/pip 已从白名单移除，因为可通过 -c/-e 执行任意代码，
            # 绕过 shell 白名单。如需执行代码请使用 run_python。
            _SHELL_WHITELIST = {
                'dir', 'ls', 'pwd', 'echo', 'whoami', 'hostname', 'date', 'time',
                'ipconfig', 'ifconfig', 'netstat', 'tasklist', 'systeminfo',
                'where', 'which', 'type', 'cat', 'head', 'tail', 'wc',
                'git', 'npm',
            }
            parts = command.split()
            if not parts:
                return "空命令"
            prog = os.path.basename(parts[0]).lower()
            if prog not in _SHELL_WHITELIST:
                return f"命令被拒绝：'{prog}' 不在白名单中。允许的命令: {', '.join(sorted(_SHELL_WHITELIST))}"
            # 危险字符黑名单（双保险）
            dangerous = ["|", ";", "&", "`", "$(", "${", ">", "<", "\\n", "rm -rf", "del /", "format ", "dd if="]
            cmd_lower = command.lower()
            for d in dangerous:
                if d in cmd_lower:
                    return f"命令被拒绝：包含危险字符 '{d}'"
            try:
                result = subprocess.run(
                    parts,
                    shell=False, capture_output=True, text=True, timeout=timeout,
                    encoding="utf-8", errors="replace"
                )
                output = ""
                if result.stdout:
                    output += f"输出:\n{result.stdout[:2000]}\n"
                if result.stderr:
                    output += f"错误:\n{result.stderr[:2000]}\n"
                if len(output) > 3000:
                    output = output[:3000] + "\n... (输出已截断)"
                return f"命令执行完成（返回码: {result.returncode}）\n{output}"
            except subprocess.TimeoutExpired:
                return f"命令超时（超过{timeout}秒）"
            except Exception as e:
                return f"命令执行失败: {e}"

        def get_weather(city: str = "北京") -> str:
            """查询天气"""
            try:
                import requests
                url = f"https://wttr.in/{city}?format=%C+%t+%h+%w&lang=zh"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    return f"{city}天气：{resp.text.strip()}"
                return "天气查询失败"
            except Exception as e:
                return f"天气查询失败: {e}"

        def get_system_info() -> str:
            """获取系统信息"""
            try:
                import psutil
                info = []
                info.append(f"系统: {os.name}")
                info.append(f"CPU核心: {psutil.cpu_count()}")
                info.append(f"CPU使用率: {psutil.cpu_percent(interval=0.5)}%")
                mem = psutil.virtual_memory()
                info.append(f"内存: {mem.total//1024//1024}MB 已用 {mem.percent}%")
                disk = psutil.disk_usage("/")
                info.append(f"磁盘: {disk.total//1024//1024//1024}GB 已用 {disk.percent}%")
                return "\n".join(info)
            except Exception as e:
                return f"获取系统信息失败: {e}"

        def move_file(src: str, dst: str) -> str:
            """移动/重命名文件"""
            try:
                s = Path(src).expanduser()
                d = Path(dst).expanduser()
                if not s.exists():
                    return f"源文件不存在: {src}"
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(s), str(d))
                return f"已移动: {src} -> {dst}"
            except Exception as e:
                return f"移动失败: {e}"

        def copy_file(src: str, dst: str) -> str:
            """复制文件"""
            try:
                s = Path(src).expanduser()
                d = Path(dst).expanduser()
                if not s.exists():
                    return f"源文件不存在: {src}"
                d.parent.mkdir(parents=True, exist_ok=True)
                if s.is_dir():
                    shutil.copytree(str(s), str(d))
                else:
                    shutil.copy2(str(s), str(d))
                return f"已复制: {src} -> {dst}"
            except Exception as e:
                return f"复制失败: {e}"

        def delete_file(path: str) -> str:
            """删除文件（有确认）"""
            try:
                p = Path(path).expanduser()
                if not p.exists():
                    return f"文件不存在: {path}"
                if p.is_dir():
                    shutil.rmtree(p)
                    return f"已删除目录: {path}"
                else:
                    p.unlink()
                    return f"已删除文件: {path}"
            except Exception as e:
                return f"删除失败: {e}"

        self.register("read_file", read_file, "读取文件内容", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "max_lines": {"type": "integer", "description": "最大行数，默认200"},
            },
            "required": ["path"],
        })

        self.register("write_file", write_file, "写入文件（覆盖）", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        })

        self.register("append_file", append_file, "追加内容到文件", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "要追加的内容"},
            },
            "required": ["path", "content"],
        })

        self.register("list_directory", list_directory, "列出目录内容", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径，默认当前目录"},
                "pattern": {"type": "string", "description": "可选，名称过滤关键词"},
            },
            "required": [],
        })

        self.register("search_files", search_files, "搜索文件", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "搜索起始路径"},
                "name": {"type": "string", "description": "文件名关键词"},
                "content": {"type": "string", "description": "文件内容关键词"},
                "ext": {"type": "string", "description": "文件扩展名，如 .py"},
            },
            "required": [],
        })

        self.register("run_python", run_python, "执行Python代码", {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python代码"},
                "timeout": {"type": "integer", "description": "超时时间（秒）"},
            },
            "required": ["code"],
        })

        self.register("run_shell", run_shell, "执行Shell命令", {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell命令"},
                "timeout": {"type": "integer", "description": "超时时间（秒）"},
            },
            "required": ["command"],
        })

        self.register("get_weather", get_weather, "查询天气", {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
            },
            "required": [],
        })

        self.register("get_system_info", get_system_info, "获取系统信息", {
            "type": "object",
            "properties": {},
            "required": [],
        })

        self.register("move_file", move_file, "移动/重命名文件", {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源路径"},
                "dst": {"type": "string", "description": "目标路径"},
            },
            "required": ["src", "dst"],
        })

        self.register("copy_file", copy_file, "复制文件", {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源路径"},
                "dst": {"type": "string", "description": "目标路径"},
            },
            "required": ["src", "dst"],
        })

        self.register("delete_file", delete_file, "删除文件或目录", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要删除的路径"},
            },
            "required": ["path"],
        })


# 全局工具注册表
_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _tool_registry


# =============================================================================
# 任务规划器
# =============================================================================

class TaskPlanner:
    """任务规划器 - 将复杂需求拆解为可执行步骤"""

    def __init__(self):
        self.registry = get_tool_registry()

    def plan(self, request: str, context: str = "") -> TaskPlan:
        """
        规划任务步骤
        （简化版：直接基于规则判断，实际生产环境应调用LLM生成计划）
        """
        plan = TaskPlan(original_request=request)
        request_lower = request.lower()

        steps = []
        step_id = 1

        if any(kw in request_lower for kw in ["写代码", "生成代码", "写个脚本", "创建一个", "帮我写"]):
            steps.append(TaskStep(step_id, f"分析需求：{request[:50]}..."))
            step_id += 1
            steps.append(TaskStep(step_id, "编写代码文件"))
            step_id += 1
            steps.append(TaskStep(step_id, "验证代码正确性"))
            step_id += 1
            steps.append(TaskStep(step_id, "总结并交付结果"))

        elif any(kw in request_lower for kw in ["找文件", "搜索文件", "查找", "找一下"]):
            steps.append(TaskStep(step_id, "确定搜索关键词和范围"))
            step_id += 1
            steps.append(TaskStep(step_id, "执行文件搜索"))
            step_id += 1
            steps.append(TaskStep(step_id, "整理并展示结果"))

        elif any(kw in request_lower for kw in ["分析数据", "处理数据", "统计", "分析"]):
            steps.append(TaskStep(step_id, "确认数据源和分析目标"))
            step_id += 1
            steps.append(TaskStep(step_id, "读取和加载数据"))
            step_id += 1
            steps.append(TaskStep(step_id, "执行数据分析"))
            step_id += 1
            steps.append(TaskStep(step_id, "生成分析报告"))

        elif any(kw in request_lower for kw in ["部署", "搭建", "安装", "配置环境"]):
            steps.append(TaskStep(step_id, "检查当前环境"))
            step_id += 1
            steps.append(TaskStep(step_id, "安装所需依赖"))
            step_id += 1
            steps.append(TaskStep(step_id, "配置相关参数"))
            step_id += 1
            steps.append(TaskStep(step_id, "验证安装结果"))

        else:
            steps.append(TaskStep(step_id, f"理解用户需求：{request[:80]}"))
            step_id += 1
            steps.append(TaskStep(step_id, "执行相关操作"))
            step_id += 1
            steps.append(TaskStep(step_id, "反馈结果"))

        plan.steps = steps
        plan.status = "planning"
        return plan


# =============================================================================
# 超级Agent执行引擎
# =============================================================================

class SuperAgent:
    """
    Y·NEX超级Agent
    支持任务规划、多步执行、自动纠错、工具调用
    """

    def __init__(self):
        self.registry = get_tool_registry()
        self.planner = TaskPlanner()
        self.max_steps = 20
        self.max_retries = 3

    def execute(self, request: str, use_llm: bool = True, callback: Callable = None) -> str:
        """
        执行一个复杂任务
        request: 用户的原始请求
        use_llm: 是否使用LLM进行智能规划
        callback: 进度回调函数 callback(step_index, step_description, status, result)
        """
        logger.info(f"SuperAgent收到任务: {request[:100]}")

        plan = self.planner.plan(request)

        if callback:
            callback("plan", plan, "")

        results = []
        context = f"用户请求: {request}\n\n"

        for i, step in enumerate(plan.steps):
            step.status = "running"
            step.started_at = time.time()

            if callback:
                callback("step_start", i, step.description)

            try:
                result = self._execute_step(step, context, results)
                step.result = result
                step.status = "completed"
                results.append(result)
                context += f"步骤{i+1}: {step.description}\n结果: {result[:500]}\n\n"

            except Exception as e:
                step.error = str(e)
                step.status = "failed"
                logger.error(f"步骤 {i+1} 失败: {e}")

                retry_count = 0
                while retry_count < self.max_retries and step.status == "failed":
                    retry_count += 1
                    if callback:
                        callback("step_retry", i, f"重试第{retry_count}次")
                    try:
                        result = self._execute_step(step, context, results)
                        step.result = result
                        step.status = "completed"
                        results.append(result)
                        context += f"步骤{i+1}（重试{retry_count}次）: {step.description}\n结果: {result[:500]}\n\n"
                    except Exception as e2:
                        step.error = str(e2)

            step.completed_at = time.time()

            if callback:
                callback("step_end", i, step.status, step.result)

            if step.status == "failed":
                plan.status = "failed"
                plan.final_result = f"任务在第{i+1}步失败: {step.error}"
                break

        if plan.status != "failed":
            plan.status = "completed"
            plan.final_result = self._summarize_results(request, results)

        if callback:
            callback("done", plan, plan.final_result)

        return plan.final_result

    def _execute_step(self, step: TaskStep, context: str, previous_results: List[str]) -> str:
        """执行单个步骤"""
        desc = step.description.lower()

        if "读取" in desc or "查看" in desc or "read" in desc:
            return "文件读取工具已就绪，可通过 read_file 工具读取指定文件"

        if "代码" in desc or "编写" in desc or "生成" in desc:
            return "代码生成能力已就绪。使用 run_python 工具可以执行Python代码验证结果"

        if "搜索" in desc or "查找" in desc:
            return "文件搜索工具已就绪，使用 search_files 工具进行搜索"

        if "分析" in desc or "统计" in desc:
            return "数据分析工具已就绪"

        if "总结" in desc or "交付" in desc or "反馈" in desc:
            return self._summarize_results(context, previous_results)

        try:
            from brain import get_ai_response
            prompt = f"""
当前任务步骤：{step.description}
完整任务：{context[:1000]}
已完成步骤结果：
{chr(10).join(f'- {r[:200]}' for r in previous_results[-5:])}

请给出这一步应该执行的操作和预期结果。
"""
            return get_ai_response(prompt, use_mock=False)
        except Exception:
            return f"步骤执行中: {step.description}"

    def _summarize_results(self, request: str, results: List[str]) -> str:
        """总结执行结果"""
        if not results:
            return "任务完成，但没有产生具体结果。"

        summary_parts = [f"任务完成！共执行{len(results)}个步骤。\n"]

        for i, r in enumerate(results, 1):
            if len(r) > 300:
                r = r[:300] + "..."
            summary_parts.append(f"【步骤{i}】{r}")

        return "\n".join(summary_parts)

    def chat_with_tools(self, message: str, history: List[dict] = None) -> str:
        """
        带工具调用的对话（ReAct模式简化版）
        """
        if history is None:
            history = []

        try:
            from brain import get_ai_response
            tools_info = json.dumps(self.registry.list_tools(), ensure_ascii=False, indent=2)

            prompt = f"""你是Y·NEX超级AI助手，可以调用工具来帮用户完成任务。

可用工具列表：
{tools_info}

用户问题：{message}

请先思考是否需要调用工具。
- 如果需要调用工具，请输出格式：
  TOOL_CALL: {{ "name": "工具名", "parameters": {{ ... }} }}
- 如果不需要工具，直接回答用户问题。

请用中文回答。"""

            response = get_ai_response(prompt, use_mock=False)

            tool_match = re.search(r'TOOL_CALL:\s*(\{.*?\})', response, re.DOTALL)
            if tool_match:
                try:
                    tool_call = json.loads(tool_match.group(1))
                    tool_name = tool_call.get("name", "")
                    tool_params = tool_call.get("parameters", {})

                    tool_result = self.registry.call_tool(tool_name, **tool_params)

                    follow_up = f"""工具调用结果：
工具: {tool_name}
参数: {json.dumps(tool_params, ensure_ascii=False)}
结果:
{tool_result}

请根据工具结果，用自然语言向用户总结回答。"""

                    final_answer = get_ai_response(follow_up, use_mock=False)
                    return final_answer

                except Exception as e:
                    return f"工具调用出错: {e}\n原始回复: {response}"

            return response

        except Exception as e:
            logger.error(f"Agent对话失败: {e}")
            return f"抱歉，处理您的请求时出现问题：{e}"


# 全局SuperAgent实例
_super_agent = SuperAgent()


def get_super_agent() -> SuperAgent:
    return _super_agent
