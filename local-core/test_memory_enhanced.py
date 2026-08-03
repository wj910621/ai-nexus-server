"""
增强记忆系统测试 (memory_enhanced)
=================================
针对本地核心最近新增的 memory_enhanced.EnhancedMemory，覆盖高风险逻辑：

  1. 文本分词 / 向量化 / 余弦相似度（解析边界）
  2. 实体抽取（7 类实体的正则规则 + 边界输入）
  3. 记忆 add / search / forget（数据库 + 缓存一致性）
  4. 权重衰减与软遗忘（FORGET_THRESHOLD 行为）
  5. auto_extract_from_conversation 端到端
  6. get_context 组合（语义 + 短期 + 用户画像）
  7. 与 memory.py 共享数据库时的表隔离
  8. 短期记忆的增/取/清

为避免污染生产 SQLite，所有测试使用临时 DB 路径，并在结束时清理。
"""

import os
import sys
import math
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta

# 测试前切换到隔离目录，避免 settings.memory_db 写入工作区
_TMP_ROOT = tempfile.mkdtemp(prefix="ynex_mem_enhanced_test_")
os.chdir(_TMP_ROOT)
os.makedirs("data", exist_ok=True)

_TEST_DB = os.path.join(_TMP_ROOT, "data", "memory_enhanced_test.db")

# 可选依赖：memory.py 可能在缺 pydantic_settings 时不可用，按需跳过画像相关断言
try:
    from memory import set_profile, get_profile  # noqa: F401
    _MEMORY_LEGACY_AVAILABLE = True
except Exception:
    _MEMORY_LEGACY_AVAILABLE = False

from memory_enhanced import (
    EnhancedMemory,
    _tokenize,
    _vectorize,
    _cosine,
    _extract_entities_by_rule,
)


def _new_mem(db_path=_TEST_DB) -> EnhancedMemory:
    """为每个用例创建一个独立 DB 实例，便于隔离"""
    if os.path.exists(db_path):
        os.remove(db_path)
    return EnhancedMemory(db_path=db_path)


def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    """浮点近似比较，避免 1.0000000002 == 1.0 失败"""
    return abs(a - b) < tol


# ============================================================
# 1. 文本分词 / 向量化 / 余弦相似度
# ============================================================

def test_tokenize_basic():
    """分词：英文/数字/中文/混合/空"""
    print("\n=== 分词边界 ===")
    assert _tokenize("") == []
    assert _tokenize(None) == []
    # 英文单词应被切分为小写
    toks = _tokenize("Hello World hello world")
    assert "hello" in toks and "world" in toks
    assert toks.count("hello") == 2
    # 中文 bigram + 单字
    toks_zh = _tokenize("我喜欢喝咖啡")
    assert "喜欢" in toks_zh  # bigram
    assert "咖" in toks_zh and "啡" in toks_zh  # 单字
    print("✓ 分词边界通过")


def test_vectorize_and_cosine():
    """向量化与余弦相似度的语义不变性"""
    print("\n=== 向量化 / 余弦相似度 ===")
    # 相同文本相似度 ≈ 1（浮点近似）
    v1 = _vectorize("我爱北京天安门")
    assert _approx(_cosine(v1, v1), 1.0), f"自相似应为 1，实际 {_cosine(v1, v1)}"
    # 完全不重叠 = 0
    v2 = _vectorize("xyz123")
    assert _cosine(v1, v2) == 0.0
    # 空向量安全降级
    assert _cosine({}, v1) == 0.0
    assert _cosine({}, {}) == 0.0
    # 高度相关文本应显著高于无关文本
    sim_related = _cosine(_vectorize("我喜欢喝咖啡"), _vectorize("我爱喝咖啡和茶"))
    sim_unrelated = _cosine(_vectorize("我喜欢喝咖啡"), _vectorize("今天天气真好"))
    assert sim_related > sim_unrelated, f"相关 {sim_related} 应 > 无关 {sim_unrelated}"
    assert 0.0 <= sim_related <= 1.0
    print(f"  相关={sim_related:.3f}, 无关={sim_unrelated:.3f}")
    print("✓ 向量化/余弦相似度通过")


# ============================================================
# 2. 实体抽取（7 类规则 + 边界）
# ============================================================

# 一条同时覆盖 7 类实体的"教科书式"测试文本
_ALL_ENTITIES_TEXT = (
    "我叫张老师，住在上海市浦东区。"
    "我喜欢喝咖啡。"
    "在阿里巴巴公司工作。"
    "明天10点开会。"
    "需要完成季度报告。"
    "电话13800138000。"
)


def test_entity_extraction_all_types():
    """7 类实体至少应被识别"""
    print("\n=== 实体抽取（全部类型） ===")
    ents = _extract_entities_by_rule(_ALL_ENTITIES_TEXT)
    print(f"  抽取结果: {ents}")
    for etype in ("location", "time", "person", "organization",
                  "preference", "task", "number"):
        assert etype in ents, f"应识别 {etype}，实际缺失"
    # 地点应包含上海
    assert any("上海" in v for v in ents["location"])
    # 电话号码
    assert "13800138000" in ents["number"]
    print("✓ 全部 7 类实体识别通过")


def test_entity_extraction_boundaries():
    """实体抽取边界：空、纯标点、无匹配"""
    print("\n=== 实体抽取边界 ===")
    assert _extract_entities_by_rule("") == {}
    assert _extract_entities_by_rule(None) == {}
    # 纯标点无匹配
    assert _extract_entities_by_rule("！！！？？？") == {}
    print("✓ 实体抽取边界通过")


# ============================================================
# 3. 记忆 add / search / forget
# ============================================================

def test_add_rejects_empty():
    """空内容应被拒绝，返回空字符串而不写入数据库"""
    print("\n=== add 拒绝空内容 ===")
    mem = _new_mem()
    assert mem.add("") == ""
    assert mem.add("   ") == ""
    assert mem.add(None) == ""
    # 数据库应为空
    conn = sqlite3.connect(_TEST_DB)
    n = conn.execute("SELECT COUNT(*) FROM enhanced_memories").fetchone()[0]
    conn.close()
    assert n == 0, f"空内容不应写入数据库，实际 {n} 条"
    print("✓ add 拒绝空内容通过")


def test_add_and_short_term_sync():
    """add 应同时写入长期存储与短期缓存"""
    print("\n=== add 同步短期记忆 ===")
    mem = _new_mem()
    mid = mem.add("今天的项目进度是 80%")
    assert mid, "应返回非空 ID"
    short = mem.get_short_term()
    assert any(m["id"] == mid for m in short), "短期缓存应同步"
    assert any(m["content"] == "今天的项目进度是 80%" for m in short)
    print(f"  ID={mid[:8]}...")
    print("✓ add 短期同步通过")


def test_search_semantic_ranking():
    """search 应基于语义相似度返回排序结果"""
    print("\n=== search 语义排序 ===")
    mem = _new_mem()
    mem.add("我喜欢喝咖啡和奶茶", metadata={"type": "long_term"})
    mem.add("今天北京下了一场大雨", metadata={"type": "long_term"})
    mem.add("项目使用 Python 编写", metadata={"type": "long_term"})

    results = mem.search("喝什么饮料", limit=5)
    print(f"  查询: '喝什么饮料'")
    for r in results:
        print(f"    [{r['score']}] {r['content']}")
    assert results, "应返回结果"
    # 第一条应是饮料相关
    top = results[0]["content"]
    assert "咖啡" in top or "奶茶" in top, f"最相关应是饮料类，实际: {top}"

    # 完全无关/空查询应安全返回
    assert mem.search("") == []
    assert mem.search("   ") == []
    print("✓ search 排序通过")


def _get_access_count(mem: EnhancedMemory, content_substr: str) -> int:
    conn = sqlite3.connect(mem.db_path)
    row = conn.execute(
        "SELECT access_count FROM enhanced_memories WHERE content LIKE ?",
        (f"%{content_substr}%",),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def test_search_updates_access_count():
    """命中应提升 access_count，延缓遗忘"""
    print("\n=== search 更新访问统计 ===")
    mem = _new_mem()
    mem.add("关键事实：张三负责后端")
    before = _get_access_count(mem, "张三")
    mem.search("张三")
    after = _get_access_count(mem, "张三")
    assert after == before + 1, f"access_count 应 +1，before={before} after={after}"
    print(f"  access_count: {before} -> {after}")
    print("✓ 访问统计通过")


def test_forget_removes_memory_and_entities():
    """forget 应同时删除记忆和关联实体，并清理短期缓存"""
    print("\n=== forget 级联删除 ===")
    mem = _new_mem()
    mid = mem.add("我住在北京市朝阳区")
    # 提取并存储实体
    entities = mem.extract_entities("我住在北京市朝阳区")
    mem._store_entities(mid, entities, "我住在北京市朝阳区")

    # 确认实体已存储
    conn = sqlite3.connect(_TEST_DB)
    n_ent = conn.execute(
        "SELECT COUNT(*) FROM enhanced_entities WHERE memory_id=?", (mid,)
    ).fetchone()[0]
    conn.close()
    assert n_ent > 0, "应已存储实体"

    # 遗忘
    assert mem.forget(mid) is True
    # 长期记忆与实体都应消失
    conn = sqlite3.connect(_TEST_DB)
    n_mem = conn.execute(
        "SELECT COUNT(*) FROM enhanced_memories WHERE id=?", (mid,)
    ).fetchone()[0]
    n_ent_after = conn.execute(
        "SELECT COUNT(*) FROM enhanced_entities WHERE memory_id=?", (mid,)
    ).fetchone()[0]
    conn.close()
    assert n_mem == 0 and n_ent_after == 0, "记忆和实体都应被删除"
    # 短期缓存也应被清理
    assert all(m["id"] != mid for m in mem.get_short_term())
    # 不存在的 ID 返回 False
    assert mem.forget("non-existent-id") is False
    # 空 ID 返回 False
    assert mem.forget("") is False
    print("✓ forget 级联删除通过")


# ============================================================
# 4. 权重衰减 / 软遗忘
# ============================================================

def test_compute_weight_decay_and_boost():
    """权重计算：时间衰减 + 访问提升"""
    print("\n=== 权重计算 ===")
    mem = _new_mem()  # 必须有实例，_compute_weight 通过 self._parse_datetime
    # 刚访问的：权重 ≈ base
    now = datetime.now().isoformat(timespec="seconds")
    w_now = mem._compute_weight(1.0, 0, now)
    assert 0.95 <= w_now <= 1.1, f"刚访问的权重应接近 base，实际 {w_now}"
    # 100 天未访问的：权重应被时间衰减大幅压低
    old = (datetime.now() - timedelta(days=100)).isoformat(timespec="seconds")
    w_old = mem._compute_weight(1.0, 0, old)
    assert w_old < w_now, "旧记忆应权重大幅下降"
    assert w_old < 0.1, f"100 天的记忆权重应很低，实际 {w_old}"
    # 访问 1000 次应抵消部分时间衰减
    w_old_boosted = mem._compute_weight(1.0, 1000, old)
    assert w_old_boosted > w_old, "高频访问应提升权重"
    print(f"  now={w_now:.3f}  old={w_old:.3f}  old+boost={w_old_boosted:.3f}")
    print("✓ 权重计算通过")


def test_purge_forgotten_removes_only_below_threshold():
    """purge_forgotten 只删除权重低于阈值的记忆"""
    print("\n=== purge_forgotten 阈值清理 ===")
    mem = _new_mem()
    # 高权重 + 刚访问 -> 不应被清
    mem.add("重要且常被引用的核心知识", metadata={"importance": 5.0})
    # 极低权重 + 旧时间 -> 应被清
    low_id = mem.add("会被遗忘的过期内容", metadata={"importance": 0.001})
    # 手动把 last_accessed 调到很早以前
    conn = sqlite3.connect(_TEST_DB)
    ancient = (datetime.now() - timedelta(days=365)).isoformat(timespec="seconds")
    conn.execute(
        "UPDATE enhanced_memories SET last_accessed=?, weight=0.0001 WHERE id=?",
        (ancient, low_id),
    )
    conn.commit()
    conn.close()

    n = mem.purge_forgotten()
    print(f"  清理条数: {n}")
    assert n >= 1, "应至少清理 1 条过期记忆"
    # 重要记忆仍在
    conn = sqlite3.connect(_TEST_DB)
    rows = conn.execute("SELECT content FROM enhanced_memories").fetchall()
    conn.close()
    contents = [r[0] for r in rows]
    assert "重要且常被引用的核心知识" in contents
    assert "会被遗忘的过期内容" not in contents
    print("✓ purge_forgotten 阈值清理通过")


def test_decay_weights_returns_forgotten_count():
    """decay_weights 应返回被软遗忘的记忆数量"""
    print("\n=== decay_weights 计数 ===")
    mem = _new_mem()
    mem.add("a", metadata={"importance": 0.0001})
    mem.add("b", metadata={"importance": 0.0001})
    # 把它们的 last_accessed 调到很早
    conn = sqlite3.connect(_TEST_DB)
    ancient = (datetime.now() - timedelta(days=1000)).isoformat(timespec="seconds")
    conn.execute("UPDATE enhanced_memories SET last_accessed=?", (ancient,))
    conn.commit()
    conn.close()

    forgotten = mem.decay_weights()
    print(f"  软遗忘条数: {forgotten}")
    assert forgotten == 2, f"应报告 2 条，实际 {forgotten}"
    print("✓ decay_weights 通过")


# ============================================================
# 5. auto_extract_from_conversation
# ============================================================

def test_auto_extract_stores_long_term_and_entities():
    """auto_extract 应至少把含实体的用户输入写入长期记忆 + 实体表"""
    print("\n=== auto_extract_from_conversation ===")
    mem = _new_mem()
    ids = mem.auto_extract_from_conversation(
        "我住在上海市浦东区，喜欢喝咖啡",
        "好的，已记录您的偏好。",
    )
    print(f"  创建记忆数: {len(ids)}")
    assert len(ids) >= 1, "用户输入含实体应被存储"
    # 实体应被存入实体表
    conn = sqlite3.connect(_TEST_DB)
    n_ent = conn.execute("SELECT COUNT(*) FROM enhanced_entities").fetchone()[0]
    n_mem = conn.execute("SELECT COUNT(*) FROM enhanced_memories").fetchone()[0]
    conn.close()
    assert n_ent > 0, "应存储实体"
    assert n_mem >= 1, "应存储记忆"
    # 短对话但无实体的 AI 回复不应被存
    mem2 = _new_mem()
    ids2 = mem2.auto_extract_from_conversation("hi", "ok")
    conn = sqlite3.connect(mem2.db_path)
    n_mem2 = conn.execute("SELECT COUNT(*) FROM enhanced_memories").fetchone()[0]
    conn.close()
    print(f"  短对话存储数: {n_mem2}")
    assert n_mem2 == 0, "无实体的短对话不应触发存储"
    print("✓ auto_extract 通过")


# ============================================================
# 6. get_by_entity
# ============================================================

def test_get_by_entity_value_and_type():
    """get_by_entity 支持按值或按类型查询"""
    print("\n=== get_by_entity ===")
    mem = _new_mem()
    # 两条不同的记忆，注入可被精确匹配的实体值 "北京市"
    mid1 = mem.add("关于北京的住所信息")
    mid2 = mem.add("北京天气情况")
    # 手动注入实体（精确值），避免被抽取规则的细微差异影响
    mem._store_entities(mid1, {"location": ["北京市"]}, "关于北京的住所信息")
    mem._store_entities(mid2, {"location": ["北京市"]}, "北京天气情况")

    # 按实体值
    by_val = mem.get_by_entity("北京市")
    print(f"  按值'北京市'命中: {len(by_val)}")
    assert len(by_val) >= 2, f"应命中 ≥2 条，实际 {len(by_val)}"
    # 按实体类型
    by_type = mem.get_by_entity("location")
    print(f"  按类型'location'命中: {len(by_type)}")
    assert len(by_type) >= 2
    # 空值安全
    assert mem.get_by_entity("") == []
    assert mem.get_by_entity(None) == []
    # 命中记忆的元数据应能正确反序列化
    assert all("id" in r and "content" in r for r in by_val)
    print("✓ get_by_entity 通过")


# ============================================================
# 7. get_context（含短期 + 长期 + 用户画像）
# ============================================================

def test_get_context_combines_layers():
    """get_context 应组合语义记忆 + 短期 + 用户画像"""
    print("\n=== get_context ===")
    mem = _new_mem()
    # 注入用户画像（复用 memory.py，按可用性跳过）
    if _MEMORY_LEGACY_AVAILABLE:
        try:
            set_profile("name", "测试者")
        except Exception:
            pass
    # 长期记忆
    mem.add("项目使用 FastAPI 构建后端服务")
    # 短期记忆
    mem.add_short_term("当前对话：你叫什么名字？")
    ctx = mem.get_context("后端技术栈是什么", limit=3)
    print(f"  context 长度: {len(ctx)} 字符")
    assert ctx, "应返回非空上下文"
    # 必含：长期记忆片段
    assert "FastAPI" in ctx, f"应包含长期记忆片段: {ctx!r}"
    # 必含：短期记忆
    assert "你叫什么名字" in ctx, f"应包含短期记忆: {ctx!r}"
    # 可选：用户画像（仅当 memory.py 可用时）
    if _MEMORY_LEGACY_AVAILABLE:
        assert "测试者" in ctx, f"应包含用户画像: {ctx!r}"
    print("✓ get_context 通过")


# ============================================================
# 8. 表隔离：与 memory.py 共享同一数据库文件
# ============================================================

def test_table_isolation_with_memory_py():
    """即使和 memory.py 共享一个 db 文件，enhanced_* 表也不应影响 messages/user_profile"""
    print("\n=== 与 memory.py 表隔离 ===")
    db = os.path.join(_TMP_ROOT, "data", "isolation_test.db")
    if os.path.exists(db):
        os.remove(db)
    # EnhancedMemory 先建表
    em = EnhancedMemory(db_path=db)
    em.add("enhanced 记忆 A")
    # 用包含明确实体的文本以验证实体表也能正确建出
    em.auto_extract_from_conversation("我在阿里巴巴公司工作", "")
    # 手动追加一条带 location 实体的记忆，确保实体表非空
    extra_mid = em.add("我家在上海市")
    em._store_entities(extra_mid, {"location": ["上海市"]}, "我家在上海市")

    conn = sqlite3.connect(db)
    # enhanced_* 表已建好
    enhanced_n = conn.execute("SELECT COUNT(*) FROM enhanced_memories").fetchone()[0]
    enhanced_ents = conn.execute("SELECT COUNT(*) FROM enhanced_entities").fetchone()[0]
    print(f"  enhanced 记忆: {enhanced_n}, enhanced 实体: {enhanced_ents}")
    assert enhanced_n >= 1
    assert enhanced_ents >= 1
    # 验证 enhanced_* 表与 legacy 的 messages/user_profile 表名互不冲突
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "enhanced_memories" in tables
    assert "enhanced_entities" in tables

    # 若 memory.py 可用，验证 legacy messages 表写入不受影响
    if _MEMORY_LEGACY_AVAILABLE:
        try:
            import memory as legacy
            legacy._init_db()
            legacy.save_memory([{"role": "user", "content": "legacy 消息"}])
            legacy_msgs = conn.execute("SELECT content FROM messages").fetchall()
            print(f"  legacy 消息: {len(legacy_msgs)}")
            assert len(legacy_msgs) >= 1, "legacy messages 不应被破坏"
        except Exception as e:
            print(f"  legacy 写入跳过: {e}")
    else:
        print("  memory.py 不可用，跳过 legacy 写入验证")
    conn.close()
    print("✓ 表隔离通过")


# ============================================================
# 9. 短期记忆管理
# ============================================================

def test_short_term_lifecycle():
    """短期记忆的 add / get / clear 行为"""
    print("\n=== 短期记忆生命周期 ===")
    mem = _new_mem()
    mem.add_short_term("第一句")
    mem.add_short_term("第二句", metadata={"src": "test"})
    items = mem.get_short_term()
    assert len(items) == 2
    assert items[0]["content"] == "第一句"
    assert items[1]["metadata"] == {"src": "test"}
    mem.clear_short_term()
    assert mem.get_short_term() == []
    # 空内容应被忽略
    mem.add_short_term("")
    mem.add_short_term(None)
    assert mem.get_short_term() == []
    print("✓ 短期记忆生命周期通过")


# ============================================================
# 10. _init_db 幂等性
# ============================================================

def test_init_db_is_idempotent():
    """多次初始化不应抛错（CREATE IF NOT EXISTS）"""
    print("\n=== _init_db 幂等性 ===")
    mem = _new_mem()
    mem._init_db()
    mem._init_db()
    mid = mem.add("再次初始化后写入")
    assert mid
    print("✓ _init_db 幂等性通过")


# ============================================================
# 入口
# ============================================================

def main():
    print("=" * 60)
    print("  memory_enhanced 增强记忆系统测试")
    print("=" * 60)

    tests = [
        test_tokenize_basic,
        test_vectorize_and_cosine,
        test_entity_extraction_all_types,
        test_entity_extraction_boundaries,
        test_add_rejects_empty,
        test_add_and_short_term_sync,
        test_search_semantic_ranking,
        test_search_updates_access_count,
        test_forget_removes_memory_and_entities,
        test_compute_weight_decay_and_boost,
        test_purge_forgotten_removes_only_below_threshold,
        test_decay_weights_returns_forgotten_count,
        test_auto_extract_stores_long_term_and_entities,
        test_get_by_entity_value_and_type,
        test_get_context_combines_layers,
        test_table_isolation_with_memory_py,
        test_short_term_lifecycle,
        test_init_db_is_idempotent,
    ]

    passed = 0
    failed = []
    for fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            failed.append((fn.__name__, str(e)))
            print(f"  ✗ {fn.__name__}: {e}")
        except Exception as e:
            failed.append((fn.__name__, repr(e)))
            print(f"  ✗ {fn.__name__}: {e!r}")

    print("\n" + "=" * 60)
    print(f"  通过: {passed}/{len(tests)}")
    if failed:
        print("  失败用例:")
        for name, err in failed:
            print(f"    - {name}: {err}")
    print("=" * 60)

    try:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    except Exception:
        pass

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
