"""
RAG 长期记忆知识库 v2
基于 ChromaDB + sentence-transformers，支持 .txt / .md 文档检索
增强：递归分块、混合检索（向量+关键词）、重排序、查询扩展、长上下文聚合
"""

import os
import re
import hashlib
import math
from collections import Counter
from typing import List, Dict, Tuple, Optional
from config import settings
from cache import cached

# 懒加载 embedding 模型和 chroma client
_embed_model = None
_chroma_client = None
_collection = None
_chromadb_warned = False
_st_warned = False

# BM25 索引缓存
_bm25_index: Optional[dict] = None
_bm25_index_version: int = -1


def _get_embed_model():
    """获取文本 embedding 模型"""
    global _embed_model, _st_warned
    if _embed_model is None:
        try:
            # 优先本地加载，避免无网络时卡死（HuggingFace 默认会多次重试）
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2",
                device="cpu",
                local_files_only=True
            )
        except Exception as e:
            err_msg = str(e)
            if not _st_warned:
                _st_warned = True
                if "Connection" in err_msg or "timeout" in err_msg.lower():
                    print("提示：无法连接 HuggingFace 下载模型，知识库需要网络。")
                elif "local_files_only" in err_msg or "not found" in err_msg.lower():
                    print("提示：本地未缓存 embedding 模型，知识库功能不可用。")
                else:
                    print(f"提示：模型加载失败（{err_msg[:60]}），知识库功能不可用。")
            return None
    return _embed_model


def _get_chroma_client():
    """获取 ChromaDB 持久化客户端"""
    global _chroma_client, _chromadb_warned
    if _chroma_client is None:
        try:
            import chromadb
        except ImportError:
            if not _chromadb_warned:
                _chromadb_warned = True
                print("提示：chromadb 未安装，知识库功能不可用。pip install chromadb 后生效。")
            return None
        os.makedirs(settings.vector_db_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.vector_db_path)
    return _chroma_client


def _get_collection():
    """获取或创建集合"""
    global _collection
    if _collection is None:
        client = _get_chroma_client()
        if client is None:
            return None
        _collection = client.get_or_create_collection(
            name="ynex_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def _split_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """简单文本分块（向后兼容）"""
    return split_text_recursive(text, chunk_size=chunk_size, overlap=overlap)


# ---------- 增强分块策略 ----------

# 默认分隔符：段落 > 句子 > 分句 > 词 > 字符
_DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "？", "！", ".", "?", "!", " ", ""]


def split_text_recursive(
    text: str,
    chunk_size: int = 400,
    overlap: int = 80,
    separators: List[str] = None,
) -> List[str]:
    """
    递归字符分块：优先按语义边界切分，避免截断句子。
    参考 LangChain RecursiveCharacterTextSplitter 思想。
    """
    separators = separators or _DEFAULT_SEPARATORS
    if not text.strip():
        return []

    # 尝试按第一个分隔符切分
    sep = separators[0]
    if sep == "":
        # 最后 fallback：按字符硬切
        return _split_text_fixed(text, chunk_size, overlap)

    parts = text.split(sep)
    if len(parts) == 1 and parts[0] == text:
        # 当前分隔符无法切分，尝试下一个
        return split_text_recursive(text, chunk_size, overlap, separators[1:])

    chunks = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        candidate = current + (sep if current else "") + part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            # 如果单段就超过 chunk_size，递归细分
            if len(part) > chunk_size:
                sub_chunks = split_text_recursive(part, chunk_size, overlap, separators[1:])
                # 最后一个子块尝试与当前剩余重叠区合并
                if current and sub_chunks:
                    merged = _merge_with_overlap(current, sub_chunks[0], overlap)
                    if merged and len(merged) <= chunk_size:
                        chunks[-1] = merged if chunks else sub_chunks[0]
                        sub_chunks = sub_chunks[1:]
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = part

    if current:
        # 保留末尾与下一个 chunk 的重叠
        if chunks:
            prev = chunks[-1]
            overlap_text = current[:overlap]
            if overlap_text and not prev.endswith(overlap_text):
                # 简单拼接保证连续性
                pass
        chunks.append(current.strip())

    return _deduplicate_chunks(chunks)


def _split_text_fixed(text: str, chunk_size: int, overlap: int) -> List[str]:
    """固定长度字符分块"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]


def _merge_with_overlap(prev: str, nxt: str, overlap: int) -> str:
    """尝试将 nxt 合并到 prev 末尾，保留 overlap"""
    if not prev or not nxt:
        return prev or nxt
    # 找 prev 末尾与 nxt 开头的最大重叠
    max_ol = min(overlap, len(prev), len(nxt))
    for i in range(max_ol, 0, -1):
        if prev[-i:] == nxt[:i]:
            return prev + nxt[i:]
    return prev + " " + nxt


def _deduplicate_chunks(chunks: List[str]) -> List[str]:
    """去除完全重复的相邻片段"""
    seen = set()
    result = []
    for c in chunks:
        key = c.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def split_text_by_markdown(text: str, chunk_size: int = 400, overlap: int = 80) -> List[Tuple[str, str]]:
    """
    Markdown 感知分块：按标题切分，返回 (heading, chunk) 元组列表。
    标题会作为元数据保留，提升检索精度。
    """
    lines = text.split("\n")
    chunks = []
    current_heading = ""
    current_body = ""

    def flush():
        nonlocal current_body
        if current_body.strip():
            sub = split_text_recursive(current_body.strip(), chunk_size, overlap)
            for s in sub:
                chunks.append((current_heading, s))
            current_body = ""

    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+", stripped):
            flush()
            current_heading = re.sub(r"^#{1,6}\s+", "", stripped)
        else:
            current_body += line + "\n"
    flush()
    return chunks


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    简单 TF 关键词提取，用于 BM25 和元数据。
    中文使用字符二元组 + 英文单词，避免把整句当作一个词。
    """
    tokens = []
    # 英文单词（2 字符以上，保留 AI、API 等缩写）
    for w in re.findall(r"[a-zA-Z]{2,}", text.lower()):
        tokens.append(w)

    # 中文字符二元组（sliding window）
    chinese_chars = re.findall(r"[\u4e00-\u9fa5]", text)
    for i in range(len(chinese_chars) - 1):
        bigram = chinese_chars[i] + chinese_chars[i + 1]
        tokens.append(bigram)

    freq = Counter(tokens)
    # 过滤常见停用词（简化版）
    stop = {
        "这个", "那个", "什么", "怎么", "可以", "进行", "使用", "通过", "需要", "我们", "你们", "他们",
        "的", "了", "在", "是", "和", "与", "或", "有", "为", "对", "我", "你", "他", "她", "它",
        "们", "就", "都", "而", "及", "等", "但", "如果", "因为", "所以", "即使", "虽然", "于是",
    }
    filtered = [(w, c) for w, c in freq.items() if w not in stop]
    return [w for w, _ in sorted(filtered, key=lambda x: x[1], reverse=True)[:top_n]]


# ---------- BM25 关键词检索 ----------

def _tokenize(text: str) -> List[str]:
    """将文本切分为用于 BM25 的 token 列表（英文单词 + 中文字符二元组）"""
    tokens = []
    for w in re.findall(r"[a-zA-Z]{2,}", text.lower()):
        tokens.append(w)
    chars = re.findall(r"[\u4e00-\u9fa5]", text)
    for i in range(len(chars) - 1):
        tokens.append(chars[i] + chars[i + 1])
    return tokens


def _compute_bm25_scores(query: str, corpus: List[str], k1: float = 1.5, b: float = 0.75) -> List[float]:
    """
    简化版 BM25 打分。
    返回与 corpus 等长的分数列表。
    """
    if not corpus:
        return []

    tokenized_corpus = [_tokenize(doc) for doc in corpus]
    avgdl = sum(len(doc) for doc in tokenized_corpus) / len(tokenized_corpus)
    if avgdl == 0:
        avgdl = 1.0

    # 计算每个词项的 IDF
    df = Counter()
    for doc in tokenized_corpus:
        seen = set(doc)
        for term in seen:
            df[term] += 1

    n = len(tokenized_corpus)
    idf = {}
    for term, f in df.items():
        idf[term] = math.log((n - f + 0.5) / (f + 0.5) + 1.0)

    query_tokens = _tokenize(query)
    scores = []
    for doc in tokenized_corpus:
        dl = len(doc)
        tf = Counter(doc)
        score = 0.0
        for term in query_tokens:
            if term not in idf:
                continue
            freq = tf.get(term, 0)
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf[term] * (freq * (k1 + 1)) / denom if denom else 0.0
        scores.append(score)
    return scores


def _build_bm25_index() -> Optional[dict]:
    """
    从 ChromaDB 构建 BM25 索引。
    返回 {version, ids, documents, sources, metadatas}。
    """
    global _bm25_index, _bm25_index_version
    collection = _get_collection()
    if collection is None:
        return None

    count = collection.count()
    if count == 0:
        return None

    # 用集合里的 ids 数量作为版本号，简单判断是否有新增/删除
    if _bm25_index is not None and _bm25_index_version == count:
        return _bm25_index

    results = collection.get(include=["documents", "metadatas"])
    docs = results.get("documents", []) or []
    ids = results.get("ids", []) or []
    metas = results.get("metadatas", []) or []

    # 取出 keywords 元数据；如果没有则现场提取
    tokenized = []
    for doc, meta in zip(docs, metas):
        keywords = (meta or {}).get("keywords", "")
        if keywords:
            tokenized.append(keywords)
        else:
            tokenized.append(doc)

    _bm25_index = {
        "version": count,
        "ids": ids,
        "documents": docs,
        "tokenized": tokenized,
        "metadatas": metas,
    }
    _bm25_index_version = count
    return _bm25_index


def invalidate_bm25_cache():
    """使 BM25 索引缓存失效，下次检索时重建"""
    global _bm25_index, _bm25_index_version
    _bm25_index = None
    _bm25_index_version = -1


def _search_bm25(query: str, top_k: int = 10) -> List[Dict]:
    """基于 BM25 的关键词检索"""
    index = _build_bm25_index()
    if index is None:
        return []

    scores = _compute_bm25_scores(query, index["tokenized"])
    ranked = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True
    )[:top_k]

    output = []
    for idx, score in ranked:
        if score <= 0:
            continue
        meta = index["metadatas"][idx] or {}
        output.append({
            "id": index["ids"][idx],
            "document": index["documents"][idx],
            "source": meta.get("source", meta.get("url", meta.get("path", "unknown"))),
            "bm25_score": score,
            "metadata": meta,
        })
    return output


# ---------- 查询扩展 ----------

def expand_query(query: str, top_n: int = 5) -> Tuple[str, List[str]]:
    """
    查询扩展：提取关键词并拼接回查询，用于增强向量检索召回。
    返回 (expanded_query, keywords)。
    """
    keywords = extract_keywords(query, top_n=top_n)
    if not keywords:
        return query, []
    expanded = query + " " + " ".join(keywords)
    return expanded, keywords


# ---------- 重排序 ----------

def rerank_results(query: str, results: List[Dict], top_k: int = None) -> List[Dict]:
    """
    轻量级重排序：综合向量距离与 BM25 关键词匹配度。
    如果 results 中已有 distance，则按距离归一化；否则使用已有顺序作为候选分。
    """
    if not results:
        return []

    # 收集文档用于 BM25 打分
    docs = [r["document"] for r in results]
    bm25_scores = _compute_bm25_scores(query, docs)

    # 归一化 BM25 分数
    max_bm25 = max(bm25_scores) if bm25_scores else 1.0
    if max_bm25 <= 0:
        max_bm25 = 1.0

    # 归一化向量距离（ChromaDB cosine distance，越小越相似）
    distances = [r.get("distance", 0.5) for r in results]
    max_dist = max(distances) if distances else 1.0
    min_dist = min(distances) if distances else 0.0
    dist_range = max_dist - min_dist if max_dist > min_dist else 1.0

    reranked = []
    for i, r in enumerate(results):
        # 向量相似度分：1 - 归一化距离
        norm_dist = (distances[i] - min_dist) / dist_range
        vector_score = 1.0 - norm_dist

        # BM25 分
        bm25_score = bm25_scores[i] / max_bm25 if i < len(bm25_scores) else 0.0

        # 融合：向量 0.6 + 关键词 0.4
        final_score = vector_score * 0.6 + bm25_score * 0.4

        item = dict(r)
        item["rerank_score"] = final_score
        item["vector_score"] = vector_score
        item["bm25_score"] = bm25_scores[i]
        reranked.append(item)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    if top_k:
        reranked = reranked[:top_k]
    return reranked


# ---------- 长上下文聚合 ----------

def aggregate_long_context(results: List[Dict], max_chars: int = 3000) -> str:
    """
    将检索结果聚合成一段长上下文，自动去重并按原文顺序拼接。
    同一来源的相邻片段会合并，减少 LLM 上下文碎片。
    """
    if not results:
        return ""

    # 按来源分组
    by_source = {}
    for r in results:
        src = r.get("source", "unknown")
        by_source.setdefault(src, []).append(r)

    parts = ["【相关知识】"]
    total_len = len(parts[0])
    idx = 1
    for source, items in by_source.items():
        # 按 chunk_index 排序（如果存在）
        items.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
        merged = []
        current = ""
        for item in items:
            doc = item["document"]
            if not current:
                current = doc
            elif doc.startswith(current[-30:]):
                current = current + doc[30:]
            else:
                merged.append(current)
                current = doc
        if current:
            merged.append(current)

        block = f"[{idx}] 来源：{source}\n" + "\n".join(merged)
        if total_len + len(block) + 4 > max_chars:
            break
        parts.append(block)
        total_len += len(block) + 4
        idx += 1

    return "\n\n".join(parts)


def _read_file(path: str) -> str:
    """读取文本文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # 尝试 gbk
        with open(path, "r", encoding="gbk") as f:
            return f.read()


def add_document(path: str, doc_id: str = None):
    """将单个文档加入知识库"""
    if not os.path.exists(path):
        print(f"文件不存在：{path}")
        return

    text = _read_file(path)
    if not text.strip():
        print(f"文件为空：{path}")
        return

    chunks = _split_text(text)
    collection = _get_collection()
    model = _get_embed_model()

    if collection is None or model is None:
        print(f"跳过 {path}：知识库依赖未就绪")
        return

    doc_id = doc_id or os.path.basename(path)
    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_{i}"
        keywords = " ".join(extract_keywords(chunk, top_n=10))
        ids.append(chunk_id)
        documents.append(chunk)
        embeddings.append(model.encode(chunk).tolist())
        metadatas.append({
            "source": path,
            "chunk_index": i,
            "keywords": keywords,
            "heading": ""
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )
    # 新增/删除文档后使 BM25 缓存失效
    invalidate_bm25_cache()
    print(f"已导入：{path}，共 {len(chunks)} 个片段")


def ingest_directory(dir_path: str = None):
    """批量导入目录下所有 .txt / .md 文档"""
    dir_path = dir_path or settings.knowledge_dir
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        print(f"知识库目录不存在，已创建：{dir_path}")
        print("请将 .txt / .md 文档放入该目录，然后重新运行。")
        return

    supported_exts = {".txt", ".md", ".markdown"}
    files = [f for f in os.listdir(dir_path) if os.path.splitext(f)[1].lower() in supported_exts]

    if not files:
        print(f"目录 {dir_path} 中没有支持的文档（.txt / .md）")
        return

    for f in files:
        add_document(os.path.join(dir_path, f))

    print(f"\n共导入 {len(files)} 个文档")


@cached(ttl=120)
def search_knowledge(
    query: str,
    top_k: int = 3,
    mode: str = "hybrid",
    rerank: bool = True,
    expand: bool = True,
    aggregate: bool = True,
) -> List[Dict]:
    """
    根据查询检索相关知识。

    参数：
        query: 查询字符串
        top_k: 返回结果数量
        mode: 检索模式，可选 vector / keyword / hybrid
        rerank: 是否启用重排序
        expand: 是否启用查询扩展
        aggregate: 是否按来源聚合相邻片段（仅影响返回结果的文档字段）
    """
    collection = _get_collection()
    if collection is None:
        return []

    model = _get_embed_model()
    if model is None:
        return []

    # 检查集合是否为空
    count = collection.count()
    if count == 0:
        return []

    # 查询扩展
    search_query = query
    if expand:
        search_query, _ = expand_query(query, top_n=5)

    vector_results = []
    keyword_results = []

    # 向量检索
    if mode in ("vector", "hybrid"):
        vec_count = min(top_k * 4, count) if mode == "hybrid" else min(top_k, count)
        results = collection.query(
            query_embeddings=[model.encode(search_query).tolist()],
            n_results=vec_count,
            include=["documents", "metadatas", "distances"]
        )
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] or {}
            vector_results.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "source": meta.get("source", meta.get("url", meta.get("path", "unknown"))),
                "distance": results["distances"][0][i],
                "metadata": meta,
            })

    # 关键词检索
    if mode in ("keyword", "hybrid"):
        keyword_results = _search_bm25(query, top_k=top_k * 4)

    # 合并去重
    merged = {}
    for r in vector_results + keyword_results:
        rid = r["id"]
        if rid not in merged:
            merged[rid] = dict(r)
        else:
            # 保留更优的距离/分数
            merged[rid]["distance"] = min(merged[rid].get("distance", 1.0), r.get("distance", 1.0))
            merged[rid]["bm25_score"] = max(merged[rid].get("bm25_score", 0.0), r.get("bm25_score", 0.0))

    candidates = list(merged.values())

    # 重排序
    if rerank and candidates:
        candidates = rerank_results(query, candidates, top_k=top_k * 2)

    # 按来源聚合相邻片段
    if aggregate and candidates:
        candidates = _aggregate_results(candidates)

    # 截取 top_k
    return candidates[:top_k]


def _aggregate_results(results: List[Dict]) -> List[Dict]:
    """
    按来源聚合相邻片段，把有重叠的文本合并为更长的上下文块。
    保留原始顺序中的第一个 chunk_index 用于排序。
    """
    if not results:
        return []

    by_source = {}
    for r in results:
        src = r.get("source", "unknown")
        by_source.setdefault(src, []).append(r)

    aggregated = []
    for src, items in by_source.items():
        items.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
        current = None
        for item in items:
            if current is None:
                current = dict(item)
            else:
                doc = item["document"]
                prev_doc = current["document"]
                # 如果下一段以当前段末尾 30 个字符开头，则合并
                overlap = 30
                if overlap and doc.startswith(prev_doc[-overlap:]):
                    current["document"] = prev_doc + doc[overlap:]
                else:
                    current["document"] = prev_doc + "\n" + doc
                current["distance"] = min(current.get("distance", 1.0), item.get("distance", 1.0))
                current["rerank_score"] = max(current.get("rerank_score", 0.0), item.get("rerank_score", 0.0))
        if current:
            aggregated.append(current)

    # 按重排序分数或向量距离排序
    aggregated.sort(
        key=lambda x: x.get("rerank_score", 1.0 - x.get("distance", 0.5)),
        reverse=True
    )
    return aggregated


def format_context(
    query: str,
    top_k: int = 3,
    max_chars: int = 3000,
    mode: str = "hybrid",
) -> str:
    """将检索结果格式化为上下文字符串，使用长上下文聚合"""
    results = search_knowledge(query, top_k=top_k, mode=mode, rerank=True, expand=True, aggregate=True)
    if not results:
        return ""

    return aggregate_long_context(results, max_chars=max_chars)
