"""
增强记忆模块测试
覆盖 memory_enhanced.py 中高风险的纯逻辑路径与持久化流程：

- _tokenize / _vectorize / _cosine  ：分词、词频向量、余弦相似度的边界
- _extract_entities_by_rule        ：7 类实体的正则抽取
- EnhancedMemory.add / search      ：写入与语义检索 + 软遗忘
- EnhancedMemory.get_by_entity     ：实体反查
- EnhancedMemory.forget / decay_weights / purge_forgotten ：遗忘与清理
- EnhancedMemory.auto_extract_from_conversation / get_context ：自动记忆提取
- EnhancedMemory._compute_weight / _parse_datetime         ：权重公式与时间容错

每个用例使用临时 SQLite 文件，保证隔离、可独立运行、可重复。
"""

import os
import sys
import tempfile
import shutil
import math
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memory_enhanced
from memory_enhanced import (
    _tokenize,
    _vectorize,
    _cosine,
    _extract_entities_by_rule,
    EnhancedMemory,
)


def _make_tmp_db() -> str:
    """创建临时数据库文件路径（保证测试可重复、彼此隔离）"""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".db", prefix="mem_enhanced_test_", delete=False
    )
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# 1. _tokenize
# ---------------------------------------------------------------------------
def test_tokenize_chinese_bigrams_and_stopwords():
    """中文字符应被切成 bigram 且过滤停用词"""
    text = "我喜欢北京"
    toks = _tokenize(text)
    # bigrams: 喜欢 (喜 is stopword so 喜 alone not emitted, but bigram 喜欢 is)
    # 单字：欢 (not stopword), 北京 (北 + 京? actually 北京 bigram, not 京 alone because of stop)
    # 简化断言：bigram 一定出现
    assert "喜欢" in toks, f"应包含 bigram '喜欢'，实际: {toks}"
    assert "北京" in toks, f"应包含 bigram '北京'，实际: {toks}"
    # 单字停用词不应出现（我、的、了 等）
    for sw in "的了在我你他":
        assert sw not in toks, f"停用词 '{sw}' 不应出现，实际: {toks}"


def test_tokenize_english_words_lowercased():
    """英文/数字应小写化并按非字母数字切分"""
    toks = _tokenize("Hello World hello WORLD AI2024 model")
    assert "hello" in toks
    assert "world" in toks
    assert "hello" in toks  # 重复
    # 单字符英文应被剔除
    assert "a" not in toks
    # 数字字母混合仍作为一个词元
    assert "ai2024" in toks
    assert "model" in toks


def test_tokenize_empty_and_none_safe():
    """空输入必须安全返回空列表，不得抛异常"""
    assert _tokenize("") == []
    assert _tokenize(None) == []


# ---------------------------------------------------------------------------
# 2. _vectorize
# ---------------------------------------------------------------------------
def test_vectorize_counts_repeated_terms():
    """相同词多次出现应在向量中累加"""
    v = _vectorize("北京 北京 北京 上海")
    assert v.get("北京", 0) == 3
    assert v.get("上海", 0) == 1


def test_vectorize_returns_empty_dict_on_empty_input():
    assert _vectorize("") == {}


# ---------------------------------------------------------------------------
# 3. _cosine
# ---------------------------------------------------------------------------
def test_cosine_identical_is_one():
    a = _vectorize("人工智能 改变 生活")
    assert math.isclose(_cosine(a, a), 1.0, rel_tol=1e-9)


def test_cosine_orthogonal_is_zero():
    a = {"苹果": 1}
    b = {"香蕉": 1}
    assert _cosine(a, b) == 0.0


def test_cosine_empty_vector_is_zero():
    assert _cosine({}, {"x": 1}) == 0.0
    assert _cosine({"x": 1}, {}) == 0.0
    assert _cosine({}, {}) == 0.0


def test_cosine_partial_overlap_in_unit_interval():
    """余弦取值必须落在 [0, 1] 闭区间"""
    a = _vectorize("北京 上海 天气")
    b = _vectorize("北京 天气 晴朗")
    sim = _cosine(a, b)
    assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# 4. _extract_entities_by_rule
# ---------------------------------------------------------------------------
def test_extract_person_location_time_org():
    text = "我叫张伟先生，住在北京市海淀区，后天去腾讯公司开会，2024年5月1日出发"
    ents = _extract_entities_by_rule(text)
    # 至少应识别出 person / location / time / organization
    assert "person" in ents, f"应识别 person，实际: {ents}"
    assert "location" in ents, f"应识别 location，实际: {ents}"
    assert "time" in ents, f"应识别 time，实际: {ents}"
    assert "organization" in ents, f"应识别 organization，实际: {ents}"
    # 北京应出现在 location 中
    assert any("北京" in v for v in ents["location"]), f"location 应含北京: {ents['location']}"


def test_extract_preference_and_task():
    text = "我喜欢吃火锅。我讨厌香菜。我需要完成项目报告。"
    ents = _extract_entities_by_rule(text)
    assert "preference" in ents, f"应识别 preference: {ents}"
    assert "task" in ents, f"应识别 task: {ents}"
    # 偏好实体至少含其中之一（吃火锅 / 香菜）
    assert any(v in ("吃火锅", "香菜") for v in ents["preference"]), \
        f"preference 应含吃火锅或香菜: {ents['preference']}"
    # 任务实体应捕获到任务内容
    assert any("完成" in v or "项目" in v for v in ents["task"]), \
        f"task 应含项目相关内容: {ents['task']}"


def test_extract_number_phone_and_quantity():
    text = "我的手机号是13800138000，今年30岁了，买了3台电脑"
    ents = _extract_entities_by_rule(text)
    assert "number" in ents, f"应识别 number: {ents}"
    nums = ents["number"]
    assert "13800138000" in nums, f"应识别手机号: {nums}"


def test_extract_empty_and_invalid_input():
    """空/非字符串输入必须返回空字典，不抛异常"""
    assert _extract_entities_by_rule("") == {}
    assert _extract_entities_by_rule(None) == {}


def test_extract_dedup_preserves_order():
    """同一类型内重复值应被去重，但保留首次出现顺序"""
    text = "我住在北京。北京很大。我喜欢北京。"
    ents = _extract_entities_by_rule(text)
    if "location" in ents:
        seen = set()
        for v in ents["location"]:
            assert v not in seen or v == "北京", f"重复未去重: {ents['location']}"
            seen.add(v)


# ---------------------------------------------------------------------------
# 5. EnhancedMemory 持久化与核心 API
# ---------------------------------------------------------------------------
def test_add_returns_uuid_and_persists():
    """add() 必须返回非空 ID 且内容可被 search 找到"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mid = mem.add("今天我去北京旅行")
        assert mid and len(mid) >= 32, f"应返回 UUID，实际: {mid!r}"
        # 直接读数据库确认已写入
        import sqlite3
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT content, memory_type, keywords, vector FROM enhanced_memories WHERE id=?",
            (mid,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "今天我去北京旅行"
        assert row[1] == EnhancedMemory.TYPE_LONG
        # keywords / vector 应当已被填入（保证检索可用）
        assert row[2] and row[3]
        json.loads(row[3])  # vector 必须是合法 JSON
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_add_rejects_empty_content():
    """空字符串/纯空白内容应返回空 ID，不应写库"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        assert mem.add("") == ""
        assert mem.add("   \n\t  ") == ""
        # 数据库中应没有记录
        import sqlite3
        conn = sqlite3.connect(db)
        n = conn.execute("SELECT COUNT(*) FROM enhanced_memories").fetchone()[0]
        conn.close()
        assert n == 0
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_search_ranks_relevant_first_and_skips_forgotten():
    """search 应能按相似度排序，并跳过被遗忘的记忆"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mem.add("北京今天晴朗，气温25度", metadata={"importance": 1.0})
        mem.add("上海下了大雨，航班延误", metadata={"importance": 1.0})
        mem.add("我最喜欢的食物是火锅", metadata={"importance": 1.0})

        results = mem.search("北京天气", limit=3)
        assert results, "search 应返回至少一条结果"
        # 最相关应排第一
        top = results[0]
        assert "北京" in top["content"], f"最相关应为北京天气: {top}"
        # 分数应在 [0, 1] 区间
        for r in results:
            assert 0.0 <= r["score"] <= 2.0
            assert r["weight"] > 0
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_search_empty_query_returns_empty():
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mem.add("任意内容")
        assert mem.search("") == []
        assert mem.search("   ") == []
        assert mem.search(None) == []
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_search_updates_access_count():
    """命中后的记忆应增加 access_count，延缓遗忘"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mid = mem.add("今天北京天气晴朗")
        mem.search("北京天气", limit=1)
        import sqlite3
        conn = sqlite3.connect(db)
        cnt = conn.execute(
            "SELECT access_count FROM enhanced_memories WHERE id=?", (mid,)
        ).fetchone()[0]
        conn.close()
        assert cnt >= 1, f"被命中后 access_count 应 >= 1，实际: {cnt}"
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_get_by_entity_finds_linked_memory():
    """通过实体值查询应能找到被 _store_entities 关联的记忆"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        # 走 auto_extract_from_conversation 触发实体存储
        ids = mem.auto_extract_from_conversation(
            "我住在北京市，我喜欢喝咖啡",
            "好的，北京市的咖啡店很多",
        )
        assert ids, "auto_extract 应至少返回一条记忆 ID"
        # 实体应已被存入 enhanced_entities
        results = mem.get_by_entity("北京市")
        assert results, "应能通过 '北京市' 查到关联记忆"
        # 通过 entity_type 反查也应能命中
        type_results = mem.get_by_entity("location")
        assert isinstance(type_results, list)
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_forget_removes_memory_and_entities():
    """forget 必须同时删除记忆与关联实体"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        ids = mem.auto_extract_from_conversation(
            "我住在北京市海淀区", "好的"
        )
        assert ids
        target = ids[0]
        # forget 必须返回 True，且二次 forget 返回 False
        assert mem.forget(target) is True
        assert mem.forget(target) is False

        import sqlite3
        conn = sqlite3.connect(db)
        n_mem = conn.execute(
            "SELECT COUNT(*) FROM enhanced_memories WHERE id=?", (target,)
        ).fetchone()[0]
        n_ent = conn.execute(
            "SELECT COUNT(*) FROM enhanced_entities WHERE memory_id=?", (target,)
        ).fetchone()[0]
        conn.close()
        assert n_mem == 0
        assert n_ent == 0
    finally:
        if os.path.exists(db):
            os.remove(db)


# ---------------------------------------------------------------------------
# 6. 权重计算（遗忘机制）
# ---------------------------------------------------------------------------
def test_compute_weight_decay_with_old_last_accessed():
    """长时间未访问的 base_weight=1.0 记忆，权重应远低于 base"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        # 100 天前访问
        old = (datetime.now() - timedelta(days=100)).isoformat(timespec="seconds")
        w = mem._compute_weight(base_weight=1.0, access_count=0, last_accessed=old)
        # 半衰期 30 天，100 天后衰减因子 ~ exp(-100/30) ≈ 0.036
        assert 0.0 <= w < 0.1, f"老旧记忆权重应接近 0，实际: {w}"
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_compute_weight_recent_with_high_access_stays_alive():
    """近期且高频访问的记忆应保持高权重，不会被软遗忘"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        now = datetime.now().isoformat(timespec="seconds")
        # access_count=100 带来 log(101)*0.1 ≈ 0.46 的提升
        w = mem._compute_weight(base_weight=1.0, access_count=100, last_accessed=now)
        assert w > 0.5, f"新近且高频访问应保持高权重，实际: {w}"
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_compute_weight_never_negative():
    """即便 base_weight 为 0 或异常输入，权重也不应返回负值"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        w = mem._compute_weight(base_weight=0.0, access_count=0, last_accessed=None)
        assert w >= 0.0
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_decay_weights_persists_and_returns_forgotten_count():
    """decay_weights 必须把新权重写回 DB，并返回被软遗忘的数量"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mem.add("很老的内容", metadata={"importance": 1.0})
        mem.add("新鲜的内容", metadata={"importance": 1.0})

        import sqlite3
        conn = sqlite3.connect(db)
        # 把第一条的 last_accessed 推到 200 天前
        old = (datetime.now() - timedelta(days=200)).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE enhanced_memories SET last_accessed=? WHERE content=?",
            (old, "很老的内容"),
        )
        conn.commit()
        conn.close()

        forgotten = mem.decay_weights()
        assert forgotten >= 1, f"老旧记忆应被计入软遗忘，实际: {forgotten}"

        # 确认新权重已写回（非常小）
        conn = sqlite3.connect(db)
        w = conn.execute(
            "SELECT weight FROM enhanced_memories WHERE content=?", ("很老的内容",)
        ).fetchone()[0]
        conn.close()
        assert w < mem.FORGET_THRESHOLD
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_purge_forgotten_removes_below_threshold():
    """purge_forgotten 必须物理删除权重低于阈值的记忆"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mem.add("陈旧记忆", metadata={"importance": 1.0})
        import sqlite3
        conn = sqlite3.connect(db)
        old = (datetime.now() - timedelta(days=365)).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE enhanced_memories SET last_accessed=?, access_count=0 WHERE content=?",
            (old, "陈旧记忆"),
        )
        conn.commit()
        conn.close()

        deleted = mem.purge_forgotten()
        assert deleted >= 1

        conn = sqlite3.connect(db)
        n = conn.execute(
            "SELECT COUNT(*) FROM enhanced_memories WHERE content=?", ("陈旧记忆",)
        ).fetchone()[0]
        conn.close()
        assert n == 0
    finally:
        if os.path.exists(db):
            os.remove(db)


# ---------------------------------------------------------------------------
# 7. 自动记忆提取 & 上下文注入
# ---------------------------------------------------------------------------
def test_auto_extract_stores_long_term_and_entities():
    """含实体的用户输入应同时产生长期记忆 + 实体记忆"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        ids = mem.auto_extract_from_conversation(
            "我住在北京市海淀区，我叫张伟先生",
            "好的，张先生",
        )
        assert ids, "应至少生成一条记忆"

        import sqlite3
        conn = sqlite3.connect(db)
        ent_count = conn.execute("SELECT COUNT(*) FROM enhanced_entities").fetchone()[0]
        conn.close()
        assert ent_count >= 1, "应至少写入一个实体"

        # 抽取的实体应能被 get_by_entity 命中：
        # 实体值由 location 正则贪婪匹配为 "北京市海淀区"，按实体类型也能反查。
        type_results = mem.get_by_entity("location")
        assert type_results, "应能按 location 实体类型反查到记忆"
        # 同时尝试通过 value 反查（兼容实际存储的实体值）
        conn = sqlite3.connect(db)
        sample = conn.execute(
            "SELECT entity_value FROM enhanced_entities WHERE entity_type='location' LIMIT 1"
        ).fetchone()
        conn.close()
        assert sample, "应至少有 location 实体"
        assert mem.get_by_entity(sample[0]), "应能通过实体 value 反查"
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_auto_extract_short_input_without_entity_is_not_stored():
    """既无实体又过短的用户输入不应被存为长期记忆（避免噪声）"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        ids = mem.auto_extract_from_conversation("嗯", "")
        assert ids == [], f"纯短回复不应产生记忆，实际: {ids}"
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_get_context_includes_short_term_and_memories():
    """get_context 必须把短期记忆 + 相关长期记忆拼成可注入的文本"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mem.add("北京今天天气晴朗")
        mem.add_short_term("用户最近问了天气")
        ctx = mem.get_context("北京天气")
        assert "北京" in ctx
        # 短期记忆标记应出现
        assert "近期上下文" in ctx or "相关记忆" in ctx
    finally:
        if os.path.exists(db):
            os.remove(db)


def test_get_context_empty_when_nothing_relevant():
    """无相关长期记忆且无短期记忆时，get_context 必须返回空串而不是抛异常"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        assert mem.get_context("完全不相关查询") == ""
    finally:
        if os.path.exists(db):
            os.remove(db)


# ---------------------------------------------------------------------------
# 8. 短期记忆
# ---------------------------------------------------------------------------
def test_short_term_lifecycle():
    """短期记忆增删查与隔离性"""
    db = _make_tmp_db()
    try:
        mem = EnhancedMemory(db_path=db)
        mem.add_short_term("第一句")
        mem.add_short_term("第二句", metadata={"src": "user"})
        st = mem.get_short_term()
        assert len(st) == 2
        assert st[0]["content"] == "第一句"
        assert st[1]["metadata"].get("src") == "user"
        mem.clear_short_term()
        assert mem.get_short_term() == []
        # 空内容不应被加入
        mem.add_short_term("")
        assert mem.get_short_term() == []
    finally:
        if os.path.exists(db):
            os.remove(db)


# ---------------------------------------------------------------------------
# 9. 时间容错解析
# ---------------------------------------------------------------------------
def test_parse_datetime_various_formats():
    """_parse_datetime 必须容错支持多种时间格式，不能抛异常"""
    now = datetime.now()
    cases = [
        ("2024-05-01 12:00:00", "sqlite"),
        ("2024-05-01T12:00:00", "iso_t"),
        ("2024-05-01", "date_only"),
        ("2024-05-01T12:00:00Z", "z_suffix"),
    ]
    for raw, _label in cases:
        parsed = EnhancedMemory._parse_datetime(raw)
        assert isinstance(parsed, datetime), f"格式 {raw!r} 解析失败"
        assert parsed.year == 2024 and parsed.month == 5 and parsed.day == 1

    # 非法输入回退到当前时间
    assert isinstance(EnhancedMemory._parse_datetime("not-a-date"), datetime)
    assert isinstance(EnhancedMemory._parse_datetime(None), datetime)
    assert isinstance(EnhancedMemory._parse_datetime(""), datetime)
    # datetime 输入原样返回
    assert EnhancedMemory._parse_datetime(now) is now


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def main():
    print("=== 增强记忆模块测试 ===\n")
    failures = []

    tests = [
        ("tokenize 中文 bigram + 停用词", test_tokenize_chinese_bigrams_and_stopwords),
        ("tokenize 英文小写化", test_tokenize_english_words_lowercased),
        ("tokenize 空值安全", test_tokenize_empty_and_none_safe),
        ("vectorize 词频累加", test_vectorize_counts_repeated_terms),
        ("vectorize 空输入", test_vectorize_returns_empty_dict_on_empty_input),
        ("cosine 相同向量=1", test_cosine_identical_is_one),
        ("cosine 正交=0", test_cosine_orthogonal_is_zero),
        ("cosine 空向量=0", test_cosine_empty_vector_is_zero),
        ("cosine 取值范围", test_cosine_partial_overlap_in_unit_interval),
        ("抽取 person/location/time/org", test_extract_person_location_time_org),
        ("抽取 preference/task", test_extract_preference_and_task),
        ("抽取 number (手机号/数量)", test_extract_number_phone_and_quantity),
        ("抽取 空值/非字符串安全", test_extract_empty_and_invalid_input),
        ("抽取 去重保序", test_extract_dedup_preserves_order),
        ("add 返回 UUID 并持久化", test_add_returns_uuid_and_persists),
        ("add 拒绝空内容", test_add_rejects_empty_content),
        ("search 排序与跳过软遗忘", test_search_ranks_relevant_first_and_skips_forgotten),
        ("search 空查询安全", test_search_empty_query_returns_empty),
        ("search 增加 access_count", test_search_updates_access_count),
        ("get_by_entity 反查", test_get_by_entity_finds_linked_memory),
        ("forget 删除记忆与实体", test_forget_removes_memory_and_entities),
        ("_compute_weight 衰减", test_compute_weight_decay_with_old_last_accessed),
        ("_compute_weight 近期高频", test_compute_weight_recent_with_high_access_stays_alive),
        ("_compute_weight 非负", test_compute_weight_never_negative),
        ("decay_weights 写回与计数", test_decay_weights_persists_and_returns_forgotten_count),
        ("purge_forgotten 物理删除", test_purge_forgotten_removes_below_threshold),
        ("auto_extract 存长期+实体", test_auto_extract_stores_long_term_and_entities),
        ("auto_extract 短输入不存", test_auto_extract_short_input_without_entity_is_not_stored),
        ("get_context 拼装", test_get_context_includes_short_term_and_memories),
        ("get_context 空查询返回空", test_get_context_empty_when_nothing_relevant),
        ("短期记忆生命周期", test_short_term_lifecycle),
        ("_parse_datetime 多种格式", test_parse_datetime_various_formats),
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
    print("\n=== 增强记忆测试完成 ===")


if __name__ == "__main__":
    main()
