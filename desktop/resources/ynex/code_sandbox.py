"""
代码执行沙箱
允许 AI 在受限环境下执行 Python 表达式或白名单 Shell 命令
所有执行都有超时和危险操作过滤
"""

import re
import ast
import math
import operator
import subprocess
import tempfile
import os
import shutil
from typing import Any

from logger import logger


# 允许执行的 Python 内置函数白名单
_SAFE_BUILTINS = {
    "abs": abs,
    "round": round,
    "max": max,
    "min": min,
    "sum": sum,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "pow": pow,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
}

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    """安全求值 AST 节点"""
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"不允许的操作：{op_type.__name__}")
        return _SAFE_OPS[op_type](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"不允许的操作：{op_type.__name__}")
        return _SAFE_OPS[op_type](_eval_node(node.operand))
    if isinstance(node, ast.Call):
        func = _eval_node(node.func)
        args = [_eval_node(a) for a in node.args]
        kwargs = {kw.arg: _eval_node(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)
    if isinstance(node, ast.Name):
        if node.id in _SAFE_BUILTINS:
            return _SAFE_BUILTINS[node.id]
        if hasattr(math, node.id):
            return getattr(math, node.id)
        raise ValueError(f"不允许的标识符：{node.id}")
    if isinstance(node, ast.Attribute):
        value = _eval_node(node.value)
        if value is math and hasattr(math, node.attr):
            return getattr(math, node.attr)
        raise ValueError(f"不允许的属性访问：{node.attr}")
    raise ValueError(f"不支持的表达式类型：{type(node).__name__}")


def safe_eval(expression: str) -> str:
    """安全计算数学表达式"""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(tree.body)
        return f"先生，计算结果：{result}"
    except Exception as e:
        return f"先生，表达式计算失败：{e}"


# Shell 命令白名单（只允许读信息，不允许修改/删除/网络）
_SHELL_WHITELIST = {
    "dir": ["dir"],
    "ls": ["ls"],
    "pwd": ["pwd"],
    "whoami": ["whoami"],
    "date": ["date"],
    "python": ["python", "--version"],
    "pip": ["pip", "list"],
    "echo": ["echo"],
}


def execute_shell(command: str) -> str:
    """执行白名单内的 Shell 命令"""
    parts = command.strip().split()
    if not parts:
        return "先生，命令为空。"

    cmd = parts[0].lower()
    if cmd not in _SHELL_WHITELIST:
        return f"先生，命令 '{cmd}' 不在安全白名单内。"

    # 防止路径穿越和重定向
    if any(c in command for c in [";", "&", "|", ">", "<", "`", "$"]):
        return "先生，检测到危险字符，拒绝执行。"

    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.expanduser("~")
        )
        output = result.stdout.strip() or result.stderr.strip() or "（无输出）"
        logger.info(f"执行 Shell：{command}")
        return f"先生，执行结果：\n{output[:1000]}"
    except subprocess.TimeoutExpired:
        return "先生，命令执行超时。"
    except Exception as e:
        return f"先生，命令执行失败：{e}"


def execute_python(code: str) -> str:
    """
    在受限沙箱中执行 Python 代码。

    安全策略：
      1. 关键字黑名单：使用子串匹配（而非 \\b 单词边界），并扩展到所有已知的
         内省/动态执行入口，避免 `__builtins__`、`getattr(__builtins__, 'eval')`
         等绕过手段。
      2. 子进程隔离：使用 -I（隔离模式，不加载 PYTHON* 环境变量与 user site）、
         -S（不加载 site-packages）、空环境变量（防止泄露密钥）、临时目录作为
         cwd，防止访问用户家目录文件。
      3. 严格超时与输出截断。
    """
    # 危险关键字过滤（子串匹配，避免 \\b__\\b 永远不匹配 __builtins__ 的绕过）
    dangerous = [
        "import", "open", "os", "sys", "subprocess",
        "eval", "exec", "compile", "__",
        "getattr", "setattr", "delattr", "hasattr",
        "globals", "locals", "vars", "dir",
        "__import__", "breakpoint", "input", "exit", "quit",
        "memoryview", "ctypes", "pickle", "marshal",
        "builtins", "fork", "spawn", "system",
    ]
    for d in dangerous:
        # 子串匹配：任何 "__" 出现即拒绝（含 __builtins__、__import__、__class__ 等）
        if d in code:
            return f"先生，代码中包含被禁用的关键字 '{d}'，拒绝执行。"

    # 二次 AST 校验：解析代码并禁止 Import / Exec / Eval 等节点
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"先生，代码语法错误：{e}"

    forbidden_nodes = (
        ast.Import, ast.ImportFrom,
    )
    # 兼容性：ast.Exec 仅在 Python 2 存在，Python 3 已移除
    if hasattr(ast, "Exec"):
        forbidden_nodes = forbidden_nodes + (ast.Exec,)
    for node in ast.walk(tree):
        if isinstance(node, forbidden_nodes):
            return f"先生，代码包含被禁止的语法结构：{type(node).__name__}，拒绝执行。"
        # 禁止任何双下划线属性访问/名字（如 __class__、__subclasses__）
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return f"先生，禁止访问下划线属性：{node.attr}，拒绝执行。"
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            return f"先生，禁止使用下划线名字：{node.id}，拒绝执行。"

    tmp_dir = tempfile.mkdtemp(prefix="ynex_sandbox_")
    try:
        tmp_path = os.path.join(tmp_dir, "snippet.py")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)

        # 隔离环境：仅保留最小 PATH，移除所有 PYTHON* 与密钥相关变量
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows 需要
        }
        result = subprocess.run(
            ["python", "-I", "-S", tmp_path],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=tmp_dir,
            env=safe_env,
        )
        output = result.stdout.strip() or result.stderr.strip() or "（无输出）"
        logger.info(f"执行 Python 代码（沙箱）：{code[:50]}...")
        return f"先生，执行结果：\n{output[:1000]}"
    except subprocess.TimeoutExpired:
        return "先生，代码执行超时。"
    except Exception as e:
        return f"先生，代码执行失败：{e}"
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# 技能入口
SKILL_MAP = {
    "safe_eval": safe_eval,
    "execute_shell": execute_shell,
    "execute_python": execute_python,
}
