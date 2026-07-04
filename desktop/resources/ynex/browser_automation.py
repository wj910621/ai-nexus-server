"""
浏览器自动化 v2 - Playwright 深度集成
支持：网页读取、搜索、截图、表单填写、点击、滚动、下载、多标签页
所有依赖懒加载，缺失时优雅降级。
"""

import re
import os
import base64
from urllib.parse import quote, urlparse
from typing import Optional, Dict, Any, List, Tuple

from logger import logger


# 单例 Playwright 实例
_pw_instance = None
_browser = None
_context = None
_pages: List[Any] = []
_current_page_idx = 0


def _ensure_browser(headless: bool = True) -> Tuple[Any, Any]:
    """确保浏览器已启动，返回 (browser, context)"""
    global _pw_instance, _browser, _context
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("未安装 Playwright。请运行：pip install playwright && playwright install")

    if _pw_instance is None:
        _pw_instance = sync_playwright().start()
        _browser = _pw_instance.chromium.launch(headless=headless)
        _context = _browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        _context.set_default_timeout(15000)
    return _browser, _context


def _current_page():
    """获取当前活跃页，没有就新建"""
    global _pages, _current_page_idx
    _, context = _ensure_browser()
    if not _pages:
        page = context.new_page()
        _pages.append(page)
        _current_page_idx = 0
    return _pages[_current_page_idx]


def close_browser():
    """关闭浏览器，释放资源"""
    global _pw_instance, _browser, _context, _pages, _current_page_idx
    try:
        if _context:
            _context.close()
        if _browser:
            _browser.close()
        if _pw_instance:
            _pw_instance.stop()
    except Exception:
        pass
    _pw_instance = None
    _browser = None
    _context = None
    _pages = []
    _current_page_idx = 0
    logger.info("浏览器已关闭")


# ---------------- 基础操作 ----------------

def goto(url: str) -> Dict[str, Any]:
    """打开网页"""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        page = _current_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return {
            "ok": True,
            "url": page.url,
            "title": page.title(),
            "tabs": len(_pages),
        }
    except Exception as e:
        logger.error(f"打开网页失败 {url}: {e}")
        return {"ok": False, "error": str(e)}


def get_page_text(max_chars: int = 3000) -> str:
    """获取当前页面可读文本"""
    try:
        page = _current_page()
        text = page.inner_text("body")
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return text
    except Exception as e:
        logger.error(f"获取页面文本失败: {e}")
        return f"获取失败：{e}"


def get_page_title() -> str:
    """获取页面标题"""
    try:
        return _current_page().title()
    except Exception as e:
        return f"获取失败：{e}"


def get_page_url() -> str:
    """获取当前页面 URL"""
    try:
        return _current_page().url
    except Exception:
        return ""


def screenshot(path: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
    """截图，返回 {ok, path, base64}"""
    try:
        page = _current_page()
        if not path:
            os.makedirs("data/screenshots", exist_ok=True)
            import time
            path = f"data/screenshots/{int(time.time())}.png"
        page.screenshot(path=path, full_page=full_page)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"ok": True, "path": path, "base64": b64[:100] + "..."}
    except Exception as e:
        logger.error(f"截图失败: {e}")
        return {"ok": False, "error": str(e)}


# ---------------- 交互操作 ----------------

def click(selector: str) -> Dict[str, Any]:
    """点击元素"""
    try:
        page = _current_page()
        page.click(selector)
        return {"ok": True, "selector": selector}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def click_text(text: str) -> Dict[str, Any]:
    """点击包含指定文本的元素"""
    try:
        page = _current_page()
        page.get_by_text(text).first.click()
        return {"ok": True, "text": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fill(selector: str, value: str) -> Dict[str, Any]:
    """填写表单"""
    try:
        page = _current_page()
        page.fill(selector, value)
        return {"ok": True, "selector": selector}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def press(key: str) -> Dict[str, Any]:
    """按下按键"""
    try:
        _current_page().keyboard.press(key)
        return {"ok": True, "key": key}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def scroll(direction: str = "down", amount: int = 500) -> Dict[str, Any]:
    """滚动页面"""
    try:
        page = _current_page()
        if direction == "down":
            page.mouse.wheel(0, amount)
        elif direction == "up":
            page.mouse.wheel(0, -amount)
        elif direction == "left":
            page.mouse.wheel(-amount, 0)
        elif direction == "right":
            page.mouse.wheel(amount, 0)
        return {"ok": True, "direction": direction, "amount": amount}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def wait(seconds: float = 1.0) -> Dict[str, Any]:
    """等待"""
    import time
    time.sleep(seconds)
    return {"ok": True, "waited": seconds}


def wait_for_selector(selector: str, timeout: int = 10000) -> Dict[str, Any]:
    """等待元素出现"""
    try:
        _current_page().wait_for_selector(selector, timeout=timeout)
        return {"ok": True, "selector": selector}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------- 多标签页 ----------------

def new_tab(url: Optional[str] = None) -> Dict[str, Any]:
    """新建标签页"""
    global _pages, _current_page_idx
    try:
        _, context = _ensure_browser()
        page = context.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _pages.append(page)
        _current_page_idx = len(_pages) - 1
        return {"ok": True, "tab_index": _current_page_idx, "total": len(_pages)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def switch_tab(index: int) -> Dict[str, Any]:
    """切换标签页"""
    global _current_page_idx
    if 0 <= index < len(_pages):
        _current_page_idx = index
        return {"ok": True, "current_index": index, "url": _pages[index].url}
    return {"ok": False, "error": f"标签页索引 {index} 超出范围 (0-{len(_pages)-1})"}


def close_tab(index: Optional[int] = None) -> Dict[str, Any]:
    """关闭标签页"""
    global _pages, _current_page_idx
    if index is None:
        index = _current_page_idx
    if 0 <= index < len(_pages):
        try:
            _pages[index].close()
        except Exception:
            pass
        _pages.pop(index)
        if _current_page_idx >= len(_pages):
            _current_page_idx = max(0, len(_pages) - 1)
        return {"ok": True, "closed_index": index, "remaining": len(_pages)}
    return {"ok": False, "error": "标签页不存在"}


def list_tabs() -> List[Dict[str, Any]]:
    """列出所有标签页"""
    result = []
    for i, page in enumerate(_pages):
        try:
            result.append({
                "index": i,
                "title": page.title(),
                "url": page.url,
                "current": i == _current_page_idx,
            })
        except Exception:
            result.append({"index": i, "title": "?", "url": "?", "current": i == _current_page_idx})
    return result


# ---------------- 搜索 ----------------

def search_web(query: str, engine: str = "bing") -> str:
    """网页搜索，返回结果摘要"""
    try:
        engines = {
            "bing": f"https://www.bing.com/search?q={quote(query)}",
            "duckduckgo": f"https://duckduckgo.com/?q={quote(query)}",
            "baidu": f"https://www.baidu.com/s?wd={quote(query)}",
        }
        url = engines.get(engine, engines["bing"])
        result = goto(url)
        if not result.get("ok"):
            return f"先生，搜索失败：{result.get('error')}"
        text = get_page_text(2000)
        return f"先生，搜索“{query}”结果：\n{text}"
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return f"先生，搜索失败：{e}"


def read_webpage(url: str, max_chars: int = 3000, use_playwright: bool = True) -> str:
    """读取网页内容，优先 Playwright（渲染 JS），失败回退 requests"""
    if use_playwright:
        try:
            result = goto(url)
            if result.get("ok"):
                text = get_page_text(max_chars)
                title = result.get("title", "")
                return f"先生，网页《{title}》内容摘要：\n{text}"
        except Exception as e:
            logger.warning(f"Playwright 读取网页失败，回退 requests: {e}")

    # 回退到 requests
    try:
        import requests
        if not url.startswith("http"):
            url = "https://" + url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
        html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return f"先生，网页内容摘要：\n{text}"
    except Exception as e:
        logger.error(f"读取网页失败: {e}")
        return f"先生，无法读取网页：{e}"


# ---------------- 智能任务执行 ----------------

def run_browser_task(task_description: str) -> str:
    """
    执行自然语言描述的浏览器任务
    支持：搜索、打开网页、截图、点击、填写、滚动、多标签等
    """
    task = task_description.strip()
    parts = re.split(r"[，。；;]\s*", task)
    results = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 打开网页
        m = re.search(r"(?:打开|访问|去|浏览)[：:]?\s*(https?://\S+|[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}\S*)", part)
        if m:
            url = m.group(1)
            r = goto(url)
            results.append(f"打开 {url}: {'成功' if r.get('ok') else r.get('error')}")
            continue

        # 搜索
        m = re.search(r"(?:搜索|搜|查|查找|查询)[：:]?\s*(.+)", part)
        if m:
            query = m.group(1).strip()
            r = search_web(query)
            results.append(r[:500])
            continue

        # 截图
        if "截图" in part or "截屏" in part or "screenshot" in part.lower():
            r = screenshot(full_page=("全页" in part or "full" in part.lower()))
            results.append(f"截图: {r.get('path') if r.get('ok') else r.get('error')}")
            continue

        # 滚动
        m = re.search(r"(?:向下|向上|向左|向右)?滚动(?:(\d+)\s*(?:像素|px)?)?", part)
        direction = "down"
        amount = 500
        if "向上" in part:
            direction = "up"
        elif "向左" in part:
            direction = "left"
        elif "向右" in part:
            direction = "right"
        m2 = re.search(r"(\d+)", part)
        if m2:
            amount = int(m2.group(1))
        if "滚动" in part:
            r = scroll(direction, amount)
            results.append(f"滚动: {'成功' if r.get('ok') else r.get('error')}")
            continue

        # 点击文本
        m = re.search(r"点击[「\"']?([^「\"'」]{1,20})[」\"']?", part)
        if m and "滚动" not in part:
            text = m.group(1).strip()
            r = click_text(text)
            results.append(f"点击「{text}」: {'成功' if r.get('ok') else r.get('error')}")
            continue

        # 新建标签页
        if "新建标签" in part or "新标签" in part:
            m = re.search(r"(?:https?://\S+)", part)
            url = m.group(0) if m else None
            r = new_tab(url)
            results.append(f"新建标签页: {'成功' if r.get('ok') else r.get('error')}")
            continue

        # 切换标签页
        m = re.search(r"切换?到?第?(\d+)[个号]?标签", part)
        if m:
            idx = int(m.group(1)) - 1
            r = switch_tab(idx)
            results.append(f"切换标签: {'成功' if r.get('ok') else r.get('error')}")
            continue

        # 关闭标签页
        if "关闭标签" in part:
            r = close_tab()
            results.append(f"关闭标签: {'成功' if r.get('ok') else r.get('error')}")
            continue

        # 等待
        m = re.search(r"等待\s*(\d+\.?\d*)\s*秒?", part)
        if m:
            secs = float(m.group(1))
            wait(secs)
            results.append(f"等待 {secs}秒")
            continue

        # 获取页面内容
        if "内容" in part or "文本" in part or "读" in part:
            text = get_page_text(1500)
            results.append(f"页面内容: {text[:300]}")
            continue

    if not results:
        # 回退：尝试直接搜索
        r = search_web(task)
        return f"先生，未能精确解析指令，已尝试搜索：\n{r}"

    return "先生，浏览器任务执行结果：\n" + "\n".join(f"{i+1}. {r}" for i, r in enumerate(results))


# ---------------- 状态查询 ----------------

def browser_status() -> Dict[str, Any]:
    """获取浏览器状态"""
    return {
        "running": _browser is not None,
        "tabs": len(_pages),
        "current_tab": _current_page_idx if _pages else -1,
        "current_url": _pages[_current_page_idx].url if _pages else "",
        "current_title": _pages[_current_page_idx].title() if _pages else "",
    }
