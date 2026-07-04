"""
Y·NEX剪贴板监听模块
实时感知用户复制的内容，并根据内容类型自动处理。

触发逻辑：
- 链接：自动打开网页/记录到知识库
- 代码片段：安全执行/保存为笔记
- 长文本：存入知识库/RAG
- 图片路径：略图描述（未实现）
- 命令行：记录到待执行队列

依赖：pyperclip
Windows 平台每 500ms 轮询一次剪贴板。
"""

import os
import re
import threading
import time
import urllib.parse
from typing import Callable, List, Optional

from logger import logger


_clipboard_thread = None
_running = False
_last_text = ""
_listeners: List[Callable[[str, str], None]] = []  # (content_type, content) -> None


def _detect_content_type(text: str) -> str:
    """识别剪贴板内容类型"""
    text = text.strip()
    if not text:
        return "empty"

    # URL
    if re.match(r"^https?://\S+", text):
        return "url"

    # 文件路径
    if re.match(r"^[a-zA-Z]:\\[^\n]*$", text) or text.startswith("/"):
        if os.path.exists(text):
            return "file_path"

    # 代码片段（包含常见代码特征）
    code_patterns = [
        r"^\s*(def|class|import|from|function|const|let|var)\s+",
        r"^\s*[#/]",
        r"[{};=]{2,}",
        r"print\(|console\.log\(",
    ]
    if any(re.search(p, text) for p in code_patterns):
        return "code"

    # 命令行
    if re.match(r"^(python|pip|node|npm|git|curl|cd|ls|dir)\s+", text):
        return "command"

    # 长文本
    if len(text) > 200:
        return "long_text"

    return "short_text"


def _handle_url(url: str):
    """处理链接：打开网页并记录到知识库"""
    logger.info(f"剪贴板检测到链接：{url}")
    try:
        from skills import SKILL_MAP
        # 自动读取网页摘要并存入知识库
        result = SKILL_MAP["read_webpage"](url)
        logger.info(f"网页读取结果：{result[:100]}")
    except Exception as e:
        logger.warning(f"链接处理失败：{e}")


def _handle_code(code: str):
    """处理代码片段"""
    logger.info("剪贴板检测到代码片段")
    try:
        # 保存到笔记
        from skills import SKILL_MAP
        title = f"剪贴板代码 {time.strftime('%m-%d %H:%M')}"
        SKILL_MAP["write_note"](title, code)
        logger.info("代码已保存到笔记")
    except Exception as e:
        logger.warning(f"代码处理失败：{e}")


def _handle_long_text(text: str):
    """处理长文本：存入知识库"""
    logger.info("剪贴板检测到大段文本")
    try:
        from knowledge_base import add_document
        add_document(text, source="clipboard")
        logger.info("文本已存入知识库")
    except Exception as e:
        logger.warning(f"知识库存储失败：{e}")


def _handle_command(cmd: str):
    """处理命令行文本"""
    logger.info(f"剪贴板检测到命令：{cmd}")
    # 仅记录，不自动执行（安全边界）
    try:
        from skills import SKILL_MAP
        title = f"待执行命令 {time.strftime('%m-%d %H:%M')}"
        SKILL_MAP["write_note"](title, cmd)
    except Exception as e:
        logger.warning(f"命令记录失败：{e}")


def _handle_file_path(path: str):
    """处理文件路径"""
    logger.info(f"剪贴板检测到文件路径：{path}")
    try:
        from skills import SKILL_MAP
        # 根据扩展名决定操作
        ext = os.path.splitext(path)[1].lower()
        if ext in [".txt", ".md", ".py", ".json"]:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            SKILL_MAP["write_note"](f"文件内容 {os.path.basename(path)}", content[:2000])
        logger.info("文件路径已处理")
    except Exception as e:
        logger.warning(f"文件路径处理失败：{e}")


def _process_clipboard_text(text: str):
    """根据类型分发处理"""
    content_type = _detect_content_type(text)

    # 记录到历史
    try:
        import pc_automation
        pc_automation.add_clipboard_record(text, content_type)
    except Exception:
        pass

    # 通知外部监听者
    for listener in _listeners:
        try:
            listener(content_type, text)
        except Exception as e:
            logger.exception(f"剪贴板监听者异常：{e}")

    if content_type == "url":
        _handle_url(text)
    elif content_type == "code":
        _handle_code(text)
    elif content_type == "long_text":
        _handle_long_text(text)
    elif content_type == "command":
        _handle_command(text)
    elif content_type == "file_path":
        _handle_file_path(text)


def _listen_loop(interval: float = 0.5):
    """剪贴板监听主循环"""
    global _last_text

    try:
        import pyperclip
    except ImportError:
        logger.warning("pyperclip 未安装，剪贴板监听不可用。")
        return

    while _running:
        try:
            current = pyperclip.paste()
            if current != _last_text and isinstance(current, str):
                _last_text = current
                _process_clipboard_text(current)
        except Exception as e:
            logger.error(f"剪贴板读取失败：{e}")
        time.sleep(interval)


def start_clipboard_listener():
    """启动剪贴板监听"""
    global _clipboard_thread, _running
    if _running:
        logger.info("剪贴板监听已在运行")
        return

    try:
        import pyperclip
    except ImportError:
        logger.warning("pyperclip 未安装，无法启动剪贴板监听。")
        return

    _running = True
    _clipboard_thread = threading.Thread(target=_listen_loop, daemon=True, name="clipboard-listener")
    _clipboard_thread.start()
    logger.info("剪贴板监听已启动")


def stop_clipboard_listener():
    """停止剪贴板监听"""
    global _running
    _running = False


def add_clipboard_listener(callback: Callable[[str, str], None]):
    """添加剪贴板内容监听回调"""
    _listeners.append(callback)


def get_last_clipboard() -> str:
    """获取最近一次剪贴板内容"""
    return _last_text


if __name__ == "__main__":
    start_clipboard_listener()
    print("剪贴板监听已启动，请复制一些内容测试。")
    time.sleep(30)
