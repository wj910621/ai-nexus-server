"""
知识库文档导入脚本

用法：
1. 将 .txt / .md 文档放入 data/knowledge/
2. 运行 python ingest_docs.py
3. 导入完成后，Y·NEX在回答问题时就能引用这些文档
"""

from knowledge_base import ingest_directory


if __name__ == "__main__":
    print("=== Y·NEX知识库导入 ===\n")
    ingest_directory()
    print("\n导入完成。")
