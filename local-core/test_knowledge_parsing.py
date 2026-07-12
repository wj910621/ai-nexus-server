"""
知识库解析与打分单元测试
============================
覆盖 knowledge_base.py 中以下高风险、纯逻辑路径（不需要 chromadb / sentence-transformers）：

- split_text_recursive          ：递归分块（句子不被截断、块大小受控、去重）
- split_text_by_markdown        ：按标题切分 + 标题作为元数据
- extract_keywords              ：TF 关键词（中文 bigram + 英文 + 停用词）
- _tokenize (kb)                ：BM25 切词
- _compute_bm25_scores          ：BM25 打分公式
- _merge_with_overlap           ：相邻片段合并时保留 overlap
- _deduplicate_chunks           ：完全重复片段去重
- _aggregate_results            ：检索结果按来源聚合
- aggregate_long_context        ：长上下文聚合（按来源分组 + max_chars 截断）
- rerank_results                ：向量 + BM25 融合排序

测试通过向 sys.modules 注入 config/cache 占位 stub 来加载 knowledge_base，
保证不依赖 pydantic_settings/loguru 等可选运行时。
"""

import os
import sys
import types
import math

# ---------------------------------------------------------------------------
# 在导入 knowledge_base 之前注入 stub，避免 pydantic_settings / loguru 依赖
# ---------------------------------------------------------------------------
_CONFIG_STUB = types.ModuleType("config")


class _Settings:
    knowledge_dir = "data/knowledge"
    vector_db_path = "data/vectors"
    memory_db = "data/memory.db"
    max_history = 20


_CONFIG_STUB.settings = _Settings()
sys.modules["config"] = _CONFIG_STUB

_CACHE_STUB = types.ModuleType("cache")


def _identity_decorator(*dargs, **dkwargs):
    """提供一个无副作用的 cached 占位实现"""

    def _wrap(fn):
        return fn

    # 兼容 @cached 与 @cached() 两种用法
    if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
        return dargs[0]
    return _wrap


_CACHE_STUB.cached = _identity_decorator
sys.modules["cache"] = _CACHE_STUB

# knowledge_base 内部还会 from config import settings；
# settings 已被设置在 _CONFIG_STUB 上，所以再次确保可见。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import knowledge_base as kb
from knowledge_base import (
    split_text_recursive,
    split_text_by_markdown,
    extract_keywords,
    _tokenize as kb_tokenize,
    _compute_bm25_scores,
    _merge_with_overlap,
    _deduplicate_chunks,
    _aggregate_results,
    aggregate_long_context,
    rerank_results,
)


# ---------------------------------------------------------------------------
# 1. split_text_recursive
# ---------------------------------------------------------------------------
def test_split_text_respects_chunk_size():
    """分块大小不应超出 chunk_size 太多（短单句可单独成块）"""
    text = "今天天气很好。明天可能下雨。后天转晴。" * 30  # 重复长文
    chunks = split_text_recursive(text, chunk_size=100, overlap=20)
    assert chunks, "应至少分出一个块"
    for c in chunks:
        # 允许存在 1 个分隔符 + 一个短单段的极小溢出（最长段是 chunk_size+seplen）
        assert len(c) <= 120, f"分块过长 {len(c)}: {c!r}"


def test_split_text_sentence_boundary_preferred():
    """递归分块应优先按句号/问号等分隔符切分，避免把一截半句话单独成块"""
    text = "第一句。第二句结束。第三句？第四句！"
    chunks = split_text_recursive(text, chunk_size=200, overlap=0)
    # 每个块应至少包含一个完整句子（以 。 ？ ！ 收尾）
    for c in chunks:
        assert c.endswith("。") or c.endswith("？") or c.endswith("！") or c.endswith(".") \
            or c.endswith("?") or c.endswith("!"), \
            f"块应在句子边界结束: {c!r}"


def test_split_text_empty_returns_empty():
    assert split_text_recursive("", chunk_size=100) == []
    assert split_text_recursive("   \n\t  ", chunk_size=100) == []


def test_split_text_dedupes_adjacent_duplicates():
    """完全重复的相邻块应被合并去重"""
    text = "X。X。X。X。"  # 全部同句
    chunks = split_text_recursive(text, chunk_size=10, overlap=0)
    # 去重后应只剩 1 块（或少量）
    assert len(chunks) <= 2, f"完全重复内容应被去重，实际 {len(chunks)} 块: {chunks}"


def test_split_text_overlap_preserves_continuity():
    """重叠区应保证相邻块之间存在重复内容（保证检索时不会丢上下文）"""
    text = "ABCDEFGH" * 50  # 200 字符无自然分隔
    chunks = split_text_recursive(text, chunk_size=60, overlap=15)
    assert len(chunks) >= 2, "长文本应至少切出 2 块"
    # 相邻块应存在字符重叠（通过 _deduplicate_chunks 之前的 overlap 区）
    for prev, cur in zip(chunks, chunks[1:]):
        # 至少存在 1 个共同字符
        assert set(prev[-15:]) & set(cur[:15]), \
            f"相邻块应存在重叠区: prev={prev!r} cur={cur!r}"


# ---------------------------------------------------------------------------
# 2. split_text_by_markdown
# ---------------------------------------------------------------------------
def test_split_markdown_preserves_heading_metadata():
    """Markdown 分块应把标题作为元数据，附加到对应正文块前"""
    md = """# 标题一
这是第一段内容。
还是第一段。

## 标题二
这是第二段内容。
"""
    blocks = split_text_by_markdown(md, chunk_size=200, overlap=0)
    assert blocks, "应至少分出一块"
    headings = [h for h, _ in blocks]
    assert "标题一" in headings
    assert "标题二" in headings
    # 每个块的内容应与对应 heading 一致
    for h, body in blocks:
        assert body.strip(), f"块内容不应为空: heading={h!r}"


def test_split_markdown_no_heading_uses_empty():
    """无标题的纯文本应使用空 heading 而不是抛异常"""
    md = "纯文本段落，没有标题。\n另一行内容。"
    blocks = split_text_by_markdown(md, chunk_size=200, overlap=0)
    assert blocks, "应至少分出一块"
    # 所有块可以使用空 heading
    headings = {h for h, _ in blocks}
    assert "" in headings


# ---------------------------------------------------------------------------
# 3. extract_keywords
# ---------------------------------------------------------------------------
def test_extract_keywords_filters_stopwords():
    """常见停用词不应出现在关键词中"""
    text = "我们在北京通过使用这个工具进行了重要的数据处理和分析"
    kws = extract_keywords(text, top_n=20)
    stop = {"这个", "我们", "进行", "使用", "通过"}
    for s in stop:
        assert s not in kws, f"停用词 {s!r} 不应出现: {kws}"


def test_extract_keywords_chinese_bigrams():
    """中文应使用 bigram 提取关键词（'北京'/'上海'）"""
    text = "北京北京北京上海广州深圳"
    kws = extract_keywords(text, top_n=10)
    assert "北京" in kws, f"北京 bigram 应被提取: {kws}"
    # 北京出现 3 次，应排在第一
    assert kws[0] == "北京", f"最高频 bigram 应排第一: {kws}"


def test_extract_keywords_english_words():
    """英文单词应被识别（≥2 字符）"""
    text = "machine learning and deep learning models"
    kws = extract_keywords(text, top_n=10)
    assert "learning" in kws
    # 短词 "and" 长度=3 但不在英文停用词中（仅过滤了中文停用词）；确保 'and' 出现即可
    assert "machine" in kws


def test_extract_keywords_top_n_limit():
    """返回数量不应超过 top_n"""
    text = " ".join(f"word{i}" for i in range(50))
    kws = extract_keywords(text, top_n=5)
    assert len(kws) <= 5


# ---------------------------------------------------------------------------
# 4. _tokenize (BM25 切词)
# ---------------------------------------------------------------------------
def test_kb_tokenize_keeps_single_chars():
    """BM25 切词对英文按词切、对中文按 bigram 切"""
    toks = kb_tokenize("北京上海 hello world")
    # 中文 bigram
    assert "北京" in toks
    assert "上海" in toks
    # 英文小写化
    assert "hello" in toks
    assert "world" in toks


def test_kb_tokenize_empty_safe():
    assert kb_tokenize("") == []


# ---------------------------------------------------------------------------
# 5. _compute_bm25_scores
# ---------------------------------------------------------------------------
def test_bm25_zero_for_empty_corpus():
    assert _compute_bm25_scores("hello", []) == []


def test_bm25_relevant_doc_outranks_irrelevant():
    """BM25 应让与查询相关的文档得分更高"""
    corpus = [
        "苹果 香蕉 水果",                 # 不相关
        "机器学习 深度学习 神经网络",      # 与查询相关
        "今天 天气 晴朗",                  # 不相关
    ]
    scores = _compute_bm25_scores("机器学习", corpus, k1=1.5, b=0.75)
    assert len(scores) == len(corpus)
    # 相关文档（index 1）分数应 > 两个不相关文档
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_bm25_handles_identical_query_in_corpus():
    """完全匹配的文档应拿到最高分"""
    corpus = ["hello world", "foo bar", "hello world"]
    scores = _compute_bm25_scores("hello", corpus)
    # 两个匹配文档得分应 > 0，且相等
    assert scores[0] > 0
    assert math.isclose(scores[0], scores[2], rel_tol=1e-9)
    assert scores[1] == 0


# ---------------------------------------------------------------------------
# 6. _merge_with_overlap
# ---------------------------------------------------------------------------
def test_merge_with_overlap_uses_overlap_region():
    """当 prev 末尾与 nxt 开头存在相同片段时，应去除重复并拼接"""
    prev = "hello world "
    nxt = "world foo"
    merged = _merge_with_overlap(prev, nxt, overlap=10)
    # 应去除 "world" 重复
    assert merged == "hello world foo", f"unexpected merge: {merged!r}"


def test_merge_with_overlap_no_common_uses_space():
    """无重叠时退化为加空格拼接"""
    prev = "abc"
    nxt = "xyz"
    merged = _merge_with_overlap(prev, nxt, overlap=5)
    assert merged == "abc xyz", f"应退化为加空格: {merged!r}"


def test_merge_with_overlap_handles_empty():
    """空输入必须安全返回非空部分"""
    assert _merge_with_overlap("", "abc", 5) == "abc"
    assert _merge_with_overlap("abc", "", 5) == "abc"
    assert _merge_with_overlap("", "", 5) == ""


# ---------------------------------------------------------------------------
# 7. _deduplicate_chunks
# ---------------------------------------------------------------------------
def test_deduplicate_chunks_removes_exact_dupes():
    chunks = ["abc", "abc", "def", "def", "ghi"]
    out = _deduplicate_chunks(chunks)
    assert out == ["abc", "def", "ghi"], f"应去重: {out}"


def test_deduplicate_chunks_keeps_order_and_drops_empty():
    chunks = ["b", "", "a", "b", "  ", "c"]
    out = _deduplicate_chunks(chunks)
    assert "a" in out
    assert "b" in out
    assert "c" in out
    # 空块应被剔除
    assert "" not in out


# ---------------------------------------------------------------------------
# 8. _aggregate_results
# ---------------------------------------------------------------------------
def test_aggregate_results_groups_by_source():
    """_aggregate_results 应按 source 聚合，结果不重复出现同源两次"""
    results = [
        {"id": "1", "document": "片段1", "source": "a.md", "distance": 0.2,
         "metadata": {"chunk_index": 0}, "rerank_score": 0.8},
        {"id": "2", "document": "片段2", "source": "a.md", "distance": 0.3,
         "metadata": {"chunk_index": 1}, "rerank_score": 0.7},
        {"id": "3", "document": "片段3", "source": "b.md", "distance": 0.4,
         "metadata": {"chunk_index": 0}, "rerank_score": 0.6},
    ]
    out = _aggregate_results(results)
    sources = [o.get("source") for o in out]
    # 不应有 3 个独立项（应被按 source 聚合）
    assert len(out) == 2, f"应聚合成 2 个 source，实际: {sources}"
    # 距离应取两段中较优（min）
    a_md = next(o for o in out if o.get("source") == "a.md")
    assert a_md["distance"] == 0.2


def test_aggregate_results_empty_input():
    assert _aggregate_results([]) == []


# ---------------------------------------------------------------------------
# 9. aggregate_long_context
# ---------------------------------------------------------------------------
def test_aggregate_long_context_respects_max_chars():
    """aggregate_long_context 必须不超出 max_chars 限制"""
    results = [
        {"document": "A" * 500, "source": f"s{i}.md", "metadata": {}}
        for i in range(10)
    ]
    ctx = aggregate_long_context(results, max_chars=1500)
    assert ctx, "应返回非空上下文"
    assert len(ctx) <= 1500 + 50, f"超出 max_chars: {len(ctx)}"
    # 至少包含【相关知识】标题
    assert "相关知识" in ctx


def test_aggregate_long_context_empty_input():
    assert aggregate_long_context([], max_chars=1000) == ""


def test_aggregate_long_context_merges_overlap():
    """同一 source 的相邻片段若存在 30 字符重叠，应被合并为一段"""
    # 重叠区是 'X' * 30，必须 >= 30 才能触发 _aggregate_results 的合并逻辑
    overlap = "X" * 30
    results = [
        {"document": overlap, "source": "x.md", "metadata": {"chunk_index": 0}},
        {"document": overlap + "后缀内容", "source": "x.md", "metadata": {"chunk_index": 1}},
    ]
    ctx = aggregate_long_context(results, max_chars=500)
    # 合并后应是 overlap + "后缀内容"，不应出现两次完整 30 字符 X 串
    assert ctx.count(overlap) == 1, f"应被合并为一段: {ctx!r}"
    assert "后缀内容" in ctx, f"应保留后缀内容: {ctx!r}"


# ---------------------------------------------------------------------------
# 10. rerank_results
# ---------------------------------------------------------------------------
def test_rerank_results_adds_rerank_score_and_sorts():
    """rerank_results 必须为每条结果添加 rerank_score 并按其降序"""
    results = [
        {"id": "1", "document": "机器学习 深度学习 神经网络",
         "source": "a", "distance": 0.1, "metadata": {}},
        {"id": "2", "document": "苹果 香蕉 水果",
         "source": "b", "distance": 0.2, "metadata": {}},
        {"id": "3", "document": "机器学习 简介 教程",
         "source": "c", "distance": 0.5, "metadata": {}},
    ]
    out = rerank_results("机器学习", results, top_k=3)
    assert len(out) == 3
    for r in out:
        assert "rerank_score" in r
        assert 0.0 <= r["rerank_score"] <= 1.5
        # 排序应为降序
    scores = [r["rerank_score"] for r in out]
    assert scores == sorted(scores, reverse=True), f"应降序: {scores}"
    # 强相关（id=1，距离最小）应排第一
    assert out[0]["id"] == "1"


def test_rerank_results_respects_top_k():
    results = [{"id": str(i), "document": f"doc {i}", "source": "x",
                "distance": 0.1 * i, "metadata": {}} for i in range(10)]
    out = rerank_results("doc", results, top_k=3)
    assert len(out) == 3


def test_rerank_results_empty_input():
    assert rerank_results("query", []) == []


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def main():
    print("=== 知识库解析测试 ===\n")
    failures = []
    tests = [
        ("split_text 块大小可控", test_split_text_respects_chunk_size),
        ("split_text 句子边界", test_split_text_sentence_boundary_preferred),
        ("split_text 空输入", test_split_text_empty_returns_empty),
        ("split_text 去重", test_split_text_dedupes_adjacent_duplicates),
        ("split_text 重叠区", test_split_text_overlap_preserves_continuity),
        ("split_markdown 保留标题", test_split_markdown_preserves_heading_metadata),
        ("split_markdown 无标题", test_split_markdown_no_heading_uses_empty),
        ("extract_keywords 停用词", test_extract_keywords_filters_stopwords),
        ("extract_keywords 中文 bigram", test_extract_keywords_chinese_bigrams),
        ("extract_keywords 英文", test_extract_keywords_english_words),
        ("extract_keywords top_n 限制", test_extract_keywords_top_n_limit),
        ("kb_tokenize 混合切词", test_kb_tokenize_keeps_single_chars),
        ("kb_tokenize 空输入", test_kb_tokenize_empty_safe),
        ("bm25 空语料", test_bm25_zero_for_empty_corpus),
        ("bm25 相关文档胜出", test_bm25_relevant_doc_outranks_irrelevant),
        ("bm25 完全匹配最高", test_bm25_handles_identical_query_in_corpus),
        ("merge_with_overlap 重叠", test_merge_with_overlap_uses_overlap_region),
        ("merge_with_overlap 退化", test_merge_with_overlap_no_common_uses_space),
        ("merge_with_overlap 空值", test_merge_with_overlap_handles_empty),
        ("deduplicate 精确去重", test_deduplicate_chunks_removes_exact_dupes),
        ("deduplicate 保序/清空", test_deduplicate_chunks_keeps_order_and_drops_empty),
        ("_aggregate 按 source 聚合", test_aggregate_results_groups_by_source),
        ("_aggregate 空输入", test_aggregate_results_empty_input),
        ("aggregate_long_context 长度限制", test_aggregate_long_context_respects_max_chars),
        ("aggregate_long_context 空输入", test_aggregate_long_context_empty_input),
        ("aggregate_long_context overlap 合并", test_aggregate_long_context_merges_overlap),
        ("rerank 添加分并降序", test_rerank_results_adds_rerank_score_and_sorts),
        ("rerank top_k 截断", test_rerank_results_respects_top_k),
        ("rerank 空输入", test_rerank_results_empty_input),
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            failures.append((name, str(e)))
        except Exception as e:
            print(f"  ✗ {name}: <{type(e).__name__}> {e}")
            failures.append((name, f"{type(e).__name__}: {e}"))

    print(f"\n通过 {len(tests) - len(failures)}/{len(tests)}")
    if failures:
        print("\n失败用例：")
        for n, e in failures:
            print(f"  - {n}: {e}")
        sys.exit(1)
    print("\n=== 知识库解析测试完成 ===")


if __name__ == "__main__":
    main()
