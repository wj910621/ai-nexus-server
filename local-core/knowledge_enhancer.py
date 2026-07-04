"""
知识库增强模块
支持：网页抓取入库、PDF/Word/PPT 解析、自动摘要、知识库管理 API
所有依赖懒加载，缺失时优雅降级。
"""

import os
import re
import hashlib
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, quote

from logger import logger


# ============================================================
# 文档解析器
# ============================================================

def parse_pdf(path: str) -> str:
    """解析 PDF 文件"""
    try:
        import PyPDF2
        text = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text() or ""
                text.append(t)
        return "\n".join(text)
    except ImportError:
        logger.warning("未安装 PyPDF2，PDF 解析不可用")
        return ""
    except Exception as e:
        logger.error(f"PDF 解析失败 {path}: {e}")
        return ""


def parse_docx(path: str) -> str:
    """解析 Word 文档"""
    try:
        from docx import Document
        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)
    except ImportError:
        logger.warning("未安装 python-docx，Word 解析不可用")
        return ""
    except Exception as e:
        logger.error(f"Word 解析失败 {path}: {e}")
        return ""


def parse_pptx(path: str) -> str:
    """解析 PPT 文档"""
    try:
        from pptx import Presentation
        prs = Presentation(path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = "".join(run.text for run in para.runs)
                        if t.strip():
                            texts.append(t)
        return "\n".join(texts)
    except ImportError:
        logger.warning("未安装 python-pptx，PPT 解析不可用")
        return ""
    except Exception as e:
        logger.error(f"PPT 解析失败 {path}: {e}")
        return ""


def parse_epub(path: str) -> str:
    """解析 EPUB 电子书"""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
        book = epub.read_epub(path)
        texts = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            texts.append(soup.get_text())
        return "\n".join(texts)
    except ImportError:
        logger.warning("未安装 EbookLib/bs4，EPUB 解析不可用")
        return ""
    except Exception as e:
        logger.error(f"EPUB 解析失败 {path}: {e}")
        return ""


def parse_text_file(path: str) -> str:
    """解析纯文本文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="gbk") as f:
                return f.read()
        except Exception:
            pass
    return ""


_PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".doc": parse_docx,
    ".pptx": parse_pptx,
    ".txt": parse_text_file,
    ".md": parse_text_file,
    ".markdown": parse_text_file,
    ".epub": parse_epub,
}


def parse_document(path: str) -> str:
    """根据扩展名自动选择解析器"""
    ext = os.path.splitext(path)[1].lower()
    parser = _PARSERS.get(ext)
    if parser:
        return parser(path)
    return ""


def get_supported_extensions() -> List[str]:
    return list(_PARSERS.keys())


# ============================================================
# 网页抓取与清洗
# ============================================================

def _extract_main_content(html: str) -> str:
    """从 HTML 中提取主要内容，移除导航、广告、页脚等"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # 移除无用元素
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
            tag.decompose()

        # 尝试找主要内容区域
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|article", re.I))
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # 清理空白行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)
    except ImportError:
        # 回退到简单正则
        html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception as e:
        logger.error(f"HTML 内容提取失败: {e}")
        return ""


def crawl_webpage(url: str, max_chars: int = 5000) -> Dict[str, Any]:
    """抓取网页内容并提取主体文本"""
    if not url.startswith("http"):
        url = "https://" + url

    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()

        title = ""
        m = re.search(r"<title>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()

        text = _extract_main_content(resp.text)
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return {
            "ok": True,
            "url": url,
            "title": title,
            "content": text,
            "length": len(text),
        }
    except Exception as e:
        logger.error(f"网页抓取失败 {url}: {e}")
        return {"ok": False, "url": url, "error": str(e)}


def add_webpage_to_knowledge(url: str) -> Dict[str, Any]:
    """抓取网页并加入知识库"""
    result = crawl_webpage(url)
    if not result.get("ok"):
        return result

    try:
        from knowledge_base import _get_collection, _get_embed_model, _split_text, extract_keywords

        collection = _get_collection()
        model = _get_embed_model()
        if collection is None or model is None:
            return {"ok": False, "error": "知识库未就绪"}

        content = result["content"]
        title = result["title"] or url
        chunks = _split_text(content, chunk_size=400, overlap=80)

        doc_id = hashlib.md5(url.encode()).hexdigest()[:12]
        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"web_{doc_id}_{i}"
            keywords = " ".join(extract_keywords(chunk, top_n=10))
            ids.append(chunk_id)
            documents.append(chunk)
            embeddings.append(model.encode(chunk).tolist())
            metadatas.append({"source": "web", "url": url, "title": title, "chunk_index": i, "keywords": keywords})

        collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        # 新增文档后使 BM25 缓存失效
        from knowledge_base import invalidate_bm25_cache
        invalidate_bm25_cache()
        logger.info(f"网页已入库：{url}，{len(chunks)} 个片段")
        return {"ok": True, "url": url, "title": title, "chunks": len(chunks)}
    except Exception as e:
        logger.error(f"网页入库失败: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# 自动摘要
# ============================================================

def summarize_text(text: str, max_sentences: int = 5) -> str:
    """
    简单抽取式摘要：按 TF 权重选择关键句子
    不需要 LLM，纯本地计算
    """
    import re
    from collections import Counter

    # 分句
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if len(sentences) <= max_sentences:
        return text

    # 简单中文分词（按字符 + 常用词）
    words = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", text)
    word_freq = Counter(w for w in words if len(w) >= 2)
    total = sum(word_freq.values())

    # 计算句子得分
    scored = []
    for i, sent in enumerate(sentences):
        sent_words = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", sent)
        score = sum(word_freq.get(w, 0) for w in sent_words) / max(len(sent_words), 1)
        scored.append((i, score, sent))

    # 取得分最高的前 N 句，保持原文顺序
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:max_sentences]
    top_sorted = sorted(top, key=lambda x: x[0])
    return "".join(s for _, _, s in top_sorted)


# ============================================================
# 知识库管理
# ============================================================

def ingest_file(path: str) -> Dict[str, Any]:
    """
    通用文件导入：支持 PDF/DOCX/PPTX/EPUB/TXT/MD
    """
    if not os.path.exists(path):
        return {"ok": False, "error": f"文件不存在：{path}"}

    text = parse_document(path)
    if not text.strip():
        return {"ok": False, "error": "无法提取文本或文件为空"}

    try:
        from knowledge_base import _get_collection, _get_embed_model, _split_text, extract_keywords, invalidate_bm25_cache

        collection = _get_collection()
        model = _get_embed_model()
        if collection is None or model is None:
            return {"ok": False, "error": "知识库未就绪"}

        chunks = _split_text(text, chunk_size=400, overlap=80)
        doc_id = os.path.basename(path)
        ids = [f"file_{hashlib.md5(path.encode()).hexdigest()[:8]}_{i}" for i in range(len(chunks))]
        embeddings = [model.encode(c).tolist() for c in chunks]
        metadatas = [
            {
                "source": "file",
                "path": path,
                "filename": doc_id,
                "chunk_index": i,
                "keywords": " ".join(extract_keywords(c, top_n=10))
            }
            for i, c in enumerate(chunks)
        ]

        collection.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        invalidate_bm25_cache()
        return {"ok": True, "path": path, "chunks": len(chunks)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ingest_directory(dir_path: str) -> Dict[str, Any]:
    """批量导入目录，支持所有可解析格式"""
    if not os.path.exists(dir_path):
        return {"ok": False, "error": f"目录不存在：{dir_path}"}

    exts = set(get_supported_extensions())
    imported = []
    failed = []

    for root, _, files in os.walk(dir_path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in exts:
                fpath = os.path.join(root, fname)
                result = ingest_file(fpath)
                if result.get("ok"):
                    imported.append(fpath)
                else:
                    failed.append({"path": fpath, "error": result.get("error", "未知错误")})

    return {"ok": True, "imported": len(imported), "failed": failed, "files": imported}


def list_knowledge_sources() -> List[Dict[str, Any]]:
    """列出知识库中的所有来源文档"""
    try:
        from knowledge_base import _get_collection
        collection = _get_collection()
        if collection is None:
            return []

        count = collection.count()
        if count == 0:
            return []

        # 取出所有元数据，按 source 聚合
        results = collection.get(include=["metadatas"])
        sources = {}
        for meta in results.get("metadatas", []):
            if not meta:
                continue
            key = meta.get("source", "unknown")
            if key not in sources:
                sources[key] = {"source": key, "chunks": 0, "title": meta.get("title", ""), "path": meta.get("path", ""), "url": meta.get("url", "")}
            sources[key]["chunks"] += 1

        return list(sources.values())
    except Exception as e:
        logger.error(f"列出知识库失败: {e}")
        return []


def delete_knowledge_source(source: str) -> Dict[str, Any]:
    """删除指定来源的所有文档片段"""
    try:
        from knowledge_base import _get_collection, invalidate_bm25_cache
        collection = _get_collection()
        if collection is None:
            return {"ok": False, "error": "知识库未就绪"}

        results = collection.get(include=["metadatas"])
        ids_to_delete = []
        for i, meta in enumerate(results.get("metadatas", [])):
            if meta and (meta.get("source") == source or meta.get("url") == source or meta.get("path") == source):
                ids_to_delete.append(results["ids"][i])

        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            invalidate_bm25_cache()

        return {"ok": True, "deleted": len(ids_to_delete)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def knowledge_status() -> Dict[str, Any]:
    """知识库状态"""
    try:
        from knowledge_base import _get_collection
        collection = _get_collection()
        if collection is None:
            return {"ok": False, "status": "unavailable"}
        count = collection.count()
        sources = list_knowledge_sources()
        return {
            "ok": True,
            "status": "ready",
            "total_chunks": count,
            "sources": len(sources),
            "supported_formats": get_supported_extensions(),
        }
    except Exception as e:
        return {"ok": False, "status": "error", "error": str(e)}
