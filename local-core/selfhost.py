"""
自托管服务接入模块
让Y·NEX可以调用以下自托管服务：

1. Paperless-ngx - 文档管理（搜索文件、上传、归档）
2. Immich - 照片/视频管理（搜索相册、上传、查看回忆）
3. n8n - 工作流自动化（触发工作流）

API 文档参考：
- Paperless: https://docs.paperless-ngx.com/api/
- Immich: https://immich.app/docs/api/
- n8n: https://docs.n8n.io/api/
"""

import os
import requests
from typing import Optional, List, Dict

from config import settings
from logger import logger


# =============================================================================
# Paperless-ngx
# =============================================================================

def _paperless_headers():
    return {"Authorization": f"Token {settings.paperless_token}"}


def _paperless_url(path: str) -> str:
    base = settings.paperless_url.rstrip("/")
    return f"{base}/api/{path.lstrip('/')}"


def paperless_available() -> bool:
    return bool(settings.paperless_url and settings.paperless_token)


def search_documents(query: str, limit: int = 5) -> str:
    """在 Paperless 中搜索文档"""
    if not paperless_available():
        return "先生，未配置 Paperless-ngx。"
    try:
        url = _paperless_url("documents/")
        params = {"query": query, "page_size": limit}
        resp = requests.get(url, headers=_paperless_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return f"先生，在 Paperless 中未找到与「{query}」相关的文档。"
        lines = [f"先生，找到 {data.get('count', 0)} 份相关文档："]
        for doc in results:
            title = doc.get("title", "未知标题")
            created = doc.get("created_date", "")
            doc_id = doc.get("id", "")
            lines.append(f"  - [{doc_id}] {title}（{created}）")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Paperless 搜索失败：{e}")
        return f"先生，搜索文档失败：{e}"


def upload_document(file_path: str, title: Optional[str] = None) -> str:
    """上传文档到 Paperless"""
    if not paperless_available():
        return "先生，未配置 Paperless-ngx。"
    if not os.path.exists(file_path):
        return f"先生，文件不存在：{file_path}"
    try:
        url = _paperless_url("documents/post_document/")
        fname = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            files = {"document": (fname, f)}
            data = {}
            if title:
                data["title"] = title
            resp = requests.post(url, headers=_paperless_headers(), files=files, data=data, timeout=60)
        resp.raise_for_status()
        return f"先生，文档已上传到 Paperless：{fname}"
    except Exception as e:
        return f"先生，上传文档失败：{e}"


# =============================================================================
# Immich
# =============================================================================

def _immich_headers():
    return {
        "x-api-key": settings.immich_api_key,
        "Accept": "application/json"
    }


def _immich_url(path: str) -> str:
    base = settings.immich_url.rstrip("/")
    return f"{base}/api/{path.lstrip('/')}"


def immich_available() -> bool:
    return bool(settings.immich_url and settings.immich_api_key)


def search_photos(query: str, limit: int = 10) -> str:
    """在 Immich 中搜索照片"""
    if not immich_available():
        return "先生，未配置 Immich。"
    try:
        url = _immich_url("search/metadata")
        params = {"query": query, "limit": limit}
        resp = requests.get(url, headers=_immich_headers(), params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            assets = data.get("assets", {}).get("items", []) if isinstance(data.get("assets"), dict) else data.get("assets", [])
            if not assets:
                return f"先生，未找到与「{query}」相关的照片。"
            lines = [f"先生，找到 {len(assets)} 张相关照片："]
            for a in assets[:limit]:
                title = a.get("originalFileName", "")
                date = a.get("fileCreatedAt", "")[:10]
                lines.append(f"  - {title}（{date}）")
            return "\n".join(lines)
        else:
            return f"先生，搜索照片失败：{resp.status_code}"
    except Exception as e:
        return f"先生，搜索照片失败：{e}"


def get_memory_lane(date: Optional[str] = None) -> str:
    """获取"历史上的今天"回忆"""
    if not immich_available():
        return "先生，未配置 Immich。"
    try:
        url = _immich_url("assets/memory-lane")
        params = {}
        if date:
            params["date"] = date
        resp = requests.get(url, headers=_immich_headers(), params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                total = len(data)
            else:
                total = 0
            if total > 0:
                return f"先生，历史上的今天有 {total} 张照片。"
            return "先生，历史上的今天没有照片。"
        return f"先生，获取回忆失败：{resp.status_code}"
    except Exception as e:
        return f"先生，获取回忆失败：{e}"


def upload_photo(file_path: str) -> str:
    """上传照片到 Immich"""
    if not immich_available():
        return "先生，未配置 Immich。"
    if not os.path.exists(file_path):
        return f"先生，文件不存在：{file_path}"
    try:
        import hashlib
        with open(file_path, "rb") as f:
            data = f.read()
        checksum = hashlib.sha1(data).hexdigest()
        url = _immich_url("assets")
        headers = _immich_headers()
        files = {"assetData": (os.path.basename(file_path), data)}
        data_form = {
            "deviceAssetId": checksum,
            "deviceId": "ynex-pc",
            "assetType": "IMAGE",
        }
        resp = requests.post(url, headers=headers, files=files, data=data_form, timeout=60)
        resp.raise_for_status()
        return f"先生，照片已上传到 Immich：{os.path.basename(file_path)}"
    except Exception as e:
        return f"先生，上传照片失败：{e}"


# =============================================================================
# n8n
# =============================================================================

def _n8n_headers():
    return {
        "X-N8N-API-KEY": settings.n8n_api_key,
        "Content-Type": "application/json"
    }


def _n8n_url(path: str) -> str:
    base = settings.n8n_url.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def n8n_available() -> bool:
    return bool(settings.n8n_url and settings.n8n_api_key)


def list_workflows(limit: int = 20) -> str:
    """列出 n8n 工作流"""
    if not n8n_available():
        return "先生，未配置 n8n。"
    try:
        url = _n8n_url("workflows")
        resp = requests.get(url, headers=_n8n_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        workflows = data.get("data", []) if isinstance(data, dict) else data
        if not workflows:
            return "先生，没有工作流。"
        lines = ["先生，可用的工作流："]
        for wf in workflows[:limit]:
            wid = wf.get("id", "")
            name = wf.get("name", "未命名")
            active = "运行中" if wf.get("active") else "已停止"
            lines.append(f"  - [{wid}] {name}（{active}）")
        return "\n".join(lines)
    except Exception as e:
        return f"先生，获取工作流失败：{e}"


def trigger_webhook(webhook_id: str, payload: Optional[dict] = None) -> str:
    """
    通过 webhook 触发 n8n 工作流。
    webhook_id 可以是完整 URL 或仅 ID。
    """
    if not n8n_available() and not webhook_id.startswith("http"):
        return "先生，未配置 n8n。"
    try:
        if webhook_id.startswith("http"):
            url = webhook_id
        else:
            url = _n8n_url(f"webhook/{webhook_id}")
        resp = requests.post(url, json=payload or {}, timeout=30)
        if resp.status_code in (200, 201, 202):
            return f"先生，工作流已触发。"
        return f"先生，触发失败：{resp.status_code}"
    except Exception as e:
        return f"先生，触发工作流失败：{e}"


# =============================================================================
# 自托管服务总览
# =============================================================================

def selfhost_status() -> str:
    """返回所有自托管服务的连接状态"""
    services = []
    if paperless_available():
        services.append("📄 Paperless-ngx：已配置")
    else:
        services.append("📄 Paperless-ngx：未配置")

    if immich_available():
        services.append("🖼️ Immich：已配置")
    else:
        services.append("🖼️ Immich：未配置")

    if n8n_available():
        services.append("🔀 n8n：已配置")
    else:
        services.append("🔀 n8n：未配置")

    return "自托管服务状态：\n" + "\n".join(services)
