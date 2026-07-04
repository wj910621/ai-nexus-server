"""
RAG 知识库测试脚本
测试文档导入、向量检索、格式化上下文
"""

import os
from knowledge_base import (
    ingest_directory,
    search_knowledge,
    format_context,
    add_document,
    expand_query,
    aggregate_long_context,
)


def setup_test_doc():
    """创建测试文档"""
    os.makedirs("data/knowledge", exist_ok=True)
    path = "data/knowledge/test_company.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "Y·NEX科技有限公司成立于 2024 年，专注于个人 AI 管家研发。\n"
            "公司口号是：让每个人都能拥有自己的 AI 管家。\n"
            "核心产品Y·NEX支持语音识别、大语言模型对话、工具调用和长期记忆。\n"
        )
    return path


def main():
    print("=== RAG 知识库测试 ===\n")

    # 1. 准备测试文档
    path = setup_test_doc()
    print(f"1. 创建测试文档：{path}")

    # 2. 导入文档
    print("\n2. 导入知识库...")
    ingest_directory("data/knowledge")

    # 3. 检索测试
    print("\n3. 混合检索测试（hybrid + 重排序 + 查询扩展）...")
    queries = [
        "Y·NEX是做什么的",
        "公司口号是什么",
        "Y·NEX有哪些功能",
    ]
    for q in queries:
        print(f"\n查询：{q}")
        expanded, keywords = expand_query(q)
        print(f"  扩展查询：{expanded} | 关键词：{keywords}")
        results = search_knowledge(q, top_k=2, mode="hybrid", rerank=True, expand=True, aggregate=True)
        for r in results:
            print(f"  来源：{r['source']}")
            print(f"  内容：{r['document'][:80]}...")
            print(f"  相似度距离：{r.get('distance', -1):.4f} | 重排序分：{r.get('rerank_score', -1):.4f}")

    # 4. 纯关键词检索
    print("\n4. 纯关键词检索测试（keyword mode）...")
    keyword_results = search_knowledge("AI 管家", top_k=2, mode="keyword", rerank=False)
    for r in keyword_results:
        print(f"  来源：{r['source']} | BM25：{r.get('bm25_score', -1):.4f}")
        print(f"  内容：{r['document'][:80]}...")

    # 5. 长上下文聚合
    print("\n5. 长上下文聚合：")
    all_results = search_knowledge("Y·NEX公司", top_k=6, mode="hybrid")
    context = aggregate_long_context(all_results, max_chars=1500)
    print(context)

    # 6. 格式化上下文
    print("\n6. 格式化上下文：")
    print(format_context("Y·NEX公司是做什么的", top_k=3))

    print("\n=== RAG 测试完成 ===")


if __name__ == "__main__":
    main()
