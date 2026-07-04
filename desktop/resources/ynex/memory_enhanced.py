"""
增强记忆系统（EnhancedMemory）
==============================
在现有 memory.py 基础之上提供更丰富的记忆能力，不替换原有模块，而是与之并存、互补。

核心能力：
    1. 短期记忆：当前对话上下文（基于内存，随进程生命周期）
    2. 长期记忆：跨对话持久化（基于 SQLite，与 memory.py 共用同一数据库文件）
    3. 实体记忆：自动从对话中提取人名、地点、时间、组织、偏好、任务、数字
    4. 语义检索：基于字符 n-gram + 词频向量的余弦相似度（零依赖实现）
    5. 自动记忆提取：从对话中识别重要信息并存储为长期记忆
    6. 遗忘机制：根据访问频率与时间衰减自动降低记忆权重

设计原则：
    - 零外部依赖：仅使用 Python 标准库（sqlite3 / re / json / math / uuid / collections）
    - 与 memory.py 隔离：使用独立表名 enhanced_memories / enhanced_entities，互不干扰
    - 向后兼容：不修改 memory.py，可被现有代码按需调用
    - 简洁 API：add / search / get_by_entity / forget / extract_entities
              / auto_extract_from_conversation / get_context
"""

import os
import re
import json
import math
import uuid
import sqlite3
from collections import Counter
from datetime import datetime

# 复用现有项目的配置（保证数据库路径一致）
try:
    from config import settings
except Exception:
    # 独立运行时使用与 config.py 一致的默认值，保证零外部依赖
    class _DefaultSettings:
        memory_db = "data/memory.db"
        max_history = 20
    settings = _DefaultSettings()

try:
    from logger import logger
except Exception:
    # 日志不可用时降级为标准 logging，避免影响核心功能
    import logging
    logger = logging.getLogger("memory_enhanced")


# ====================================================================
# 工具函数：文本分词与向量化（零依赖实现）
# ====================================================================

# 中文停用词（高频但语义弱的单字）
_STOPWORDS = set("的了着过是我在你他她它们个么呢吧啊呀哦嗯这那地得也都很还就")


def _tokenize(text: str) -> list:
    """
    简单分词（中英文混合）：
      - 英文/数字：按非字母数字边界切分为词元
      - 中文：提取单字（去停用词）+ 字符 bigram（更好捕捉语义单元）
    返回 token 列表，保留顺序可重复，用于构建词频向量。
    """
    if not text:
        return []
    tokens = []
    # 英文/数字词元
    for m in re.finditer(r"[A-Za-z0-9_]+", text):
        w = m.group(0).lower()
        if len(w) > 1:
            tokens.append(w)
    # 中文字符序列
    for m in re.finditer(r"[\u4e00-\u9fa5]+", text):
        seg = m.group(0)
        # 单字（去停用词）
        for ch in seg:
            if ch not in _STOPWORDS:
                tokens.append(ch)
        # bigram：相邻两字组合，近似词语
        for i in range(len(seg) - 1):
            tokens.append(seg[i:i + 2])
    return tokens


def _vectorize(text: str) -> dict:
    """将文本转为稀疏词频向量 {token: tf}"""
    toks = _tokenize(text)
    if not toks:
        return {}
    return dict(Counter(toks))


def _cosine(vec_a: dict, vec_b: dict) -> float:
    """计算两个稀疏词频向量的余弦相似度，取值 [0, 1]"""
    if not vec_a or not vec_b:
        return 0.0
    # 在较小向量上迭代以加速
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
    dot = 0.0
    for k, v in vec_a.items():
        if k in vec_b:
            dot += v * vec_b[k]
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ====================================================================
# 实体抽取规则（基于正则与关键词，零 NLP 依赖）
# ====================================================================

# 每条规则：(实体类型, [正则模式...])，匹配 group(1) 为实体值
_ENTITY_RULES = [
    # 人名：我叫XX / 是XX / XX先生/女士/老师
    ("person", [
        r"我[叫是]([\u4e00-\u9fa5A-Za-z]{2,6}?)(?:先生|女士|老师|同学|老板|经理|工程师|[,，。!！\s]|$)",
        r"([\u4e00-\u9fa5]{2,4})(?:先生|女士|老师|同学)",
    ]),
    # 地点：在/住/去/来自 + XX市/省/县/区
    ("location", [
        r"(?:在|住在|住于|去|到|来自|位于)([\u4e00-\u9fa5]{2,8}(?:市|省|县|区|镇|村|路|街|号))",
        r"([\u4e00-\u9fa5]{2,6}(?:市|省|县|区))",
    ]),
    # 时间：日期 / 相对时间 / 时刻
    ("time", [
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
        r"(\d{1,2}月\d{1,2}日)",
        r"(明天|今天|后天|昨天|大后天|下周|下个月|明年|今年|现在)",
        r"(\d{1,2}点(?:\d{1,2}分)?)",
    ]),
    # 组织：XX公司/大学/部门
    ("organization", [
        r"([\u4e00-\u9fa5A-Za-z]{2,10}(?:公司|集团|大学|学院|部门|机构|组织|团队|工作室))",
    ]),
    # 偏好：我喜欢/讨厌/偏好 + 内容
    ("preference", [
        r"我(?:喜欢|爱|偏好|钟爱|讨厌|不喜欢|厌恶)([\u4e00-\u9fa5A-Za-z0-9]{1,20})",
        r"我(?:的)?(?:偏好|爱好|喜好)是([\u4e00-\u9fa5A-Za-z0-9]{1,20})",
    ]),
    # 任务：需要做/计划做/要完成
    ("task", [
        r"(?:需要|得|要|计划|准备|打算)([\u4e00-\u9fa5A-Za-z0-9]{2,30})",
    ]),
    # 数字：电话/数量
    ("number", [
        r"(1[3-9]\d{9})",                                   # 手机号
        r"(\d{3,4}-\d{7,8})",                               # 座机
        r"(\d+(?:\.\d+)?)\s*(个|件|本|台|份|次|岁|年|月|天|小时|分钟)",  # 数量+量词
    ]),
]


def _extract_entities_by_rule(text: str) -> dict:
    """
    基于规则提取实体，返回 {实体类型: [值1, 值2, ...]}。
    使用正则匹配，避免引入 NLP 库。
    """
    if not text:
        return {}
    result = {}
    for etype, patterns in _ENTITY_RULES:
        found = []
        for pat in patterns:
            for m in re.finditer(pat, text):
                val = m.group(1).strip()
                # 过滤过短或过长的噪声
                if val and 1 <= len(val) <= 30:
                    found.append(val)
        if found:
            # 去重保序
            seen = set()
            uniq = []
            for v in found:
                if v not in seen:
                    seen.add(v)
                    uniq.append(v)
            result[etype] = uniq
    return result


# ====================================================================
# 增强记忆主类
# ====================================================================

class EnhancedMemory:
    """
    增强记忆系统主类。

    与 memory.py 共用同一个 SQLite 数据库文件（settings.memory_db），
    但使用独立的表名（enhanced_memories / enhanced_entities），互不干扰。
    """

    # 记忆类型常量
    TYPE_SHORT = "short_term"   # 短期记忆（当前对话）
    TYPE_LONG = "long_term"     # 长期记忆（跨对话持久化）
    TYPE_ENTITY = "entity"     # 实体记忆

    # 遗忘机制参数
    FORGET_HALF_LIFE_DAYS = 30.0   # 权重半衰期：30 天后权重衰减到约 0.37
    FORGET_THRESHOLD = 0.05        # 低于此权重的记忆在检索时被忽略（软遗忘）
    SEARCH_CANDIDATE_LIMIT = 300   # 单次语义检索最多加载的候选数量

    def __init__(self, db_path: str = None):
        """
        初始化增强记忆系统。

        :param db_path: SQLite 数据库路径，默认复用 settings.memory_db
        """
        self.db_path = db_path or settings.memory_db
        # 短期记忆缓存（当前对话上下文，进程内）
        self._short_term: list = []
        self._init_db()

    # ----------------------------------------------------------------
    # 数据库初始化与连接
    # ----------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（与 memory.py 同一文件，但表隔离）"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _init_db(self):
        """初始化增强记忆所需的数据表（不影响 memory.py 的现有表）"""
        conn = self._get_conn()
        try:
            # 长期记忆表：存储跨对话的持久化记忆
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    memory_type TEXT NOT NULL,
                    keywords TEXT,
                    vector TEXT,
                    weight REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 实体表：存储从记忆中提取的实体
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_entities (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    memory_id TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 索引：加速按类型/权重/实体值查询
            conn.execute("CREATE INDEX IF NOT EXISTS idx_em_type ON enhanced_memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_em_weight ON enhanced_memories(weight)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ee_type ON enhanced_entities(entity_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ee_value ON enhanced_entities(entity_value)")
            conn.commit()
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # 遗忘机制：权重计算
    # ----------------------------------------------------------------
    @staticmethod
    def _parse_datetime(value) -> datetime:
        """容错解析数据库中的时间字符串"""
        if not value:
            return datetime.now()
        if isinstance(value, datetime):
            return value
        s = str(value).replace("Z", "").strip()
        # 兼容 SQLite 的 "YYYY-MM-DD HH:MM:SS" 与 ISO 格式
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return datetime.now()

    def _compute_weight(self, base_weight: float, access_count: int, last_accessed) -> float:
        """
        根据访问频率与时间衰减计算当前权重。

        权重 = base_weight * 时间衰减因子 + 访问提升因子
        - 时间衰减：exp(-days / 半衰期)，访问越久权重越低
        - 访问提升：log(1 + access_count) * 0.1，被访问越多权重越高
        """
        last = self._parse_datetime(last_accessed)
        days = max((datetime.now() - last).total_seconds() / 86400.0, 0.0)
        time_decay = math.exp(-days / self.FORGET_HALF_LIFE_DAYS)
        access_boost = math.log(1 + access_count) * 0.1
        return max(base_weight * time_decay + access_boost, 0.0)

    # ----------------------------------------------------------------
    # 基础 API：添加记忆
    # ----------------------------------------------------------------
    def add(self, content, metadata=None) -> str:
        """
        添加一条记忆，返回记忆 ID。

        :param content: 记忆文本内容
        :param metadata: 可选的元数据字典（可包含 type / source / importance 等）
        :return: 记忆 ID（UUID），失败返回空字符串
        """
        if not content or not content.strip():
            return ""
        content = content.strip()
        memory_id = str(uuid.uuid4())
        meta = metadata if isinstance(metadata, dict) else {}
        meta_json = json.dumps(meta, ensure_ascii=False)

        # 文本向量化（词频向量 + 关键词集合）
        tokens = _tokenize(content)
        keywords = " ".join(sorted(set(tokens)))
        vector = json.dumps(_vectorize(content), ensure_ascii=False)

        # 记忆类型：优先取 metadata.type，否则默认长期记忆
        mtype = meta.get("type", self.TYPE_LONG)
        # 重要度作为初始权重
        weight = float(meta.get("importance", 1.0))

        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO enhanced_memories
                   (id, content, metadata, memory_type, keywords, vector, weight, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (memory_id, content, meta_json, mtype, keywords, vector, weight)
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"添加记忆失败: {e}")
            return ""
        finally:
            conn.close()

        # 同步写入短期记忆缓存
        self._short_term.append({
            "id": memory_id,
            "content": content,
            "metadata": meta,
        })
        return memory_id

    # ----------------------------------------------------------------
    # 语义检索
    # ----------------------------------------------------------------
    def search(self, query, limit=5) -> list:
        """
        语义搜索：基于向量余弦相似度 + 关键词重叠，返回排序后的记忆列表。

        会自动过滤掉权重低于遗忘阈值的记忆（软遗忘），
        并在命中时更新对应记忆的访问次数与最近访问时间。

        :param query: 查询文本
        :param limit: 最多返回条数
        :return: [{"id","content","metadata","score","weight","memory_type","created_at"}, ...]
        """
        if not query or not query.strip():
            return []
        query = query.strip()
        q_vec = _vectorize(query)
        q_tokens = set(_tokenize(query))

        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM enhanced_memories ORDER BY weight DESC LIMIT ?",
                (self.SEARCH_CANDIDATE_LIMIT,)
            ).fetchall()
        finally:
            conn.close()

        scored = []
        touched_ids = []
        for r in rows:
            # 应用遗忘机制：权重低于阈值的跳过
            cur_weight = self._compute_weight(
                r["weight"], r["access_count"], r["last_accessed"]
            )
            if cur_weight < self.FORGET_THRESHOLD:
                continue

            # 向量相似度
            vec = json.loads(r["vector"]) if r["vector"] else {}
            sim = _cosine(q_vec, vec)
            # 关键词重叠加分
            kws = set(r["keywords"].split()) if r["keywords"] else set()
            overlap = len(q_tokens & kws)
            score = sim + overlap * 0.1
            if score <= 0:
                continue
            scored.append((score, r, cur_weight))

        if not scored:
            return []

        # 按综合得分降序
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, r, cur_weight in scored[:limit]:
            results.append({
                "id": r["id"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "score": round(score, 4),
                "weight": round(cur_weight, 4),
                "memory_type": r["memory_type"],
                "created_at": r["created_at"],
            })
            touched_ids.append(r["id"])

        # 更新被命中记忆的访问统计（提升其权重，延缓遗忘）
        if touched_ids:
            self._touch_many(touched_ids)

        return results

    def _touch_many(self, memory_ids: list):
        """批量更新记忆的访问次数与最近访问时间，并刷新权重"""
        if not memory_ids:
            return
        now = datetime.now().isoformat(timespec="seconds")
        conn = self._get_conn()
        try:
            for mid in memory_ids:
                conn.execute(
                    """UPDATE enhanced_memories
                       SET access_count = access_count + 1,
                           last_accessed = ?,
                           updated_at = ?
                       WHERE id = ?""",
                    (now, now, mid)
                )
            conn.commit()
        except Exception as e:
            logger.warning(f"更新访问统计失败: {e}")
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # 实体查询
    # ----------------------------------------------------------------
    def get_by_entity(self, entity) -> list:
        """
        按实体值或实体类型查询关联记忆。

        :param entity: 实体值（如 "北京"）或实体类型（如 "person"）
        :return: 关联记忆列表
        """
        if not entity:
            return []
        conn = self._get_conn()
        try:
            # 先按实体值精确匹配，再按类型匹配
            rows = conn.execute(
                """SELECT DISTINCT m.*
                   FROM enhanced_memories m
                   LEFT JOIN enhanced_entities e ON e.memory_id = m.id
                   WHERE e.entity_value = ? OR e.entity_type = ?
                   ORDER BY m.created_at DESC""",
                (entity, entity)
            ).fetchall()
        finally:
            conn.close()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "memory_type": r["memory_type"],
                "created_at": r["created_at"],
            })
        return results

    # ----------------------------------------------------------------
    # 遗忘机制
    # ----------------------------------------------------------------
    def forget(self, memory_id) -> bool:
        """
        主动遗忘一条记忆：从数据库中删除该记忆及其关联实体。

        :param memory_id: 记忆 ID
        :return: 是否删除成功
        """
        if not memory_id:
            return False
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "DELETE FROM enhanced_memories WHERE id = ?", (memory_id,)
            )
            conn.execute(
                "DELETE FROM enhanced_entities WHERE memory_id = ?", (memory_id,)
            )
            conn.commit()
            deleted = cur.rowcount > 0
        except Exception as e:
            logger.warning(f"遗忘记忆失败: {e}")
            return False
        finally:
            conn.close()

        # 同时从短期缓存移除
        self._short_term = [m for m in self._short_term if m.get("id") != memory_id]
        return deleted

    def decay_weights(self) -> int:
        """
        执行一次全量权重衰减：重新计算所有记忆的当前权重并持久化。
        建议定期调用（如每日一次）以让遗忘机制生效。

        :return: 被软遗忘（权重低于阈值）的记忆数量
        """
        conn = self._get_conn()
        forgotten = 0
        try:
            rows = conn.execute(
                "SELECT id, weight, access_count, last_accessed FROM enhanced_memories"
            ).fetchall()
            now = datetime.now().isoformat(timespec="seconds")
            for r in rows:
                cur_weight = self._compute_weight(
                    r["weight"], r["access_count"], r["last_accessed"]
                )
                conn.execute(
                    "UPDATE enhanced_memories SET weight = ?, updated_at = ? WHERE id = ?",
                    (cur_weight, now, r["id"])
                )
                if cur_weight < self.FORGET_THRESHOLD:
                    forgotten += 1
            conn.commit()
        except Exception as e:
            logger.warning(f"权重衰减失败: {e}")
        finally:
            conn.close()
        return forgotten

    def purge_forgotten(self) -> int:
        """
        清理已被遗忘（权重低于阈值）的记忆，物理删除以释放空间。

        :return: 被删除的记忆数量
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, weight, access_count, last_accessed FROM enhanced_memories"
            ).fetchall()
            ids_to_delete = []
            for r in rows:
                cur_weight = self._compute_weight(
                    r["weight"], r["access_count"], r["last_accessed"]
                )
                if cur_weight < self.FORGET_THRESHOLD:
                    ids_to_delete.append(r["id"])
            for mid in ids_to_delete:
                conn.execute("DELETE FROM enhanced_memories WHERE id = ?", (mid,))
                conn.execute("DELETE FROM enhanced_entities WHERE memory_id = ?", (mid,))
            conn.commit()
            return len(ids_to_delete)
        except Exception as e:
            logger.warning(f"清理遗忘记忆失败: {e}")
            return 0
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # 实体提取
    # ----------------------------------------------------------------
    def extract_entities(self, text) -> dict:
        """
        从文本中提取实体，返回 {实体类型: [值, ...]}。

        实体类型包括：person / location / time / organization / preference / task / number
        使用正则规则匹配，不依赖 NLP 库。

        :param text: 待提取的文本
        :return: 实体字典
        """
        if not text or not isinstance(text, str):
            return {}
        return _extract_entities_by_rule(text)

    def _store_entities(self, memory_id: str, entities: dict, context: str = ""):
        """将提取的实体存入实体表，关联到指定记忆"""
        if not entities or not memory_id:
            return
        conn = self._get_conn()
        try:
            for etype, values in entities.items():
                for val in values:
                    conn.execute(
                        """INSERT INTO enhanced_entities
                           (id, entity_type, entity_value, memory_id, context)
                           VALUES (?, ?, ?, ?, ?)""",
                        (str(uuid.uuid4()), etype, val, memory_id, context[:200])
                    )
            conn.commit()
        except Exception as e:
            logger.warning(f"存储实体失败: {e}")
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # 自动记忆提取
    # ----------------------------------------------------------------
    def auto_extract_from_conversation(self, user_input, ai_response) -> list:
        """
        从一轮对话中自动提取重要信息并存储为长期记忆 + 实体记忆。

        提取策略：
          1. 对 user_input 与 ai_response 分别做实体抽取
          2. 将含实体的用户输入存为长期记忆（用户的事实/偏好更重要）
          3. 将 AI 回复中的关键事实存为长期记忆
          4. 所有提取出的实体存入实体表并关联到对应记忆

        :param user_input: 用户输入文本
        :param ai_response: AI 回复文本
        :return: 新创建的记忆 ID 列表
        """
        created_ids = []

        # 提取用户输入中的实体与事实
        user_text = user_input or ""
        ai_text = ai_response or ""

        user_entities = self.extract_entities(user_text)
        ai_entities = self.extract_entities(ai_text)

        # 用户输入若含实体或足够长，存为长期记忆
        if user_text.strip():
            should_store = bool(user_entities) or len(user_text) > 15
            if should_store:
                mid = self.add(
                    user_text,
                    metadata={
                        "type": self.TYPE_LONG,
                        "source": "user",
                        "importance": 1.2 if user_entities else 0.8,
                    }
                )
                if mid:
                    created_ids.append(mid)
                    self._store_entities(mid, user_entities, user_text)

        # AI 回复中含实体或关键信息时也存储
        if ai_text.strip():
            should_store = bool(ai_entities) or len(ai_text) > 30
            if should_store:
                mid = self.add(
                    ai_text,
                    metadata={
                        "type": self.TYPE_LONG,
                        "source": "ai",
                        "importance": 0.8 if ai_entities else 0.5,
                    }
                )
                if mid:
                    created_ids.append(mid)
                    self._store_entities(mid, ai_entities, ai_text)

        if created_ids:
            logger.debug(f"自动提取 {len(created_ids)} 条记忆，实体: user={list(user_entities)} ai={list(ai_entities)}")
        return created_ids

    # ----------------------------------------------------------------
    # 获取上下文（供 system prompt 注入）
    # ----------------------------------------------------------------
    def get_context(self, query, limit=5) -> str:
        """
        根据查询获取相关记忆上下文，格式化为可注入 prompt 的字符串。

        包含：
          - 与 query 语义相关的长期记忆
          - 当前短期记忆（最近对话）
          - 可选的用户画像摘要（来自 memory.py 的 user_profile）

        :param query: 当前查询/用户输入
        :param limit: 最多包含的相关长期记忆条数
        :return: 格式化的上下文字符串（无内容时返回空串）
        """
        parts = []

        # 1. 语义检索相关长期记忆
        memories = self.search(query, limit=limit)
        if memories:
            lines = []
            for m in memories:
                lines.append(f"- {m['content']}")
            parts.append("【相关记忆】\n" + "\n".join(lines))

        # 2. 短期记忆（当前对话最近几条）
        recent_short = self._short_term[-3:] if self._short_term else []
        if recent_short:
            lines = [f"- {m['content']}" for m in recent_short]
            parts.append("【近期上下文】\n" + "\n".join(lines))

        # 3. 用户画像（复用 memory.py，保持兼容）
        try:
            from memory import get_profile
            profile_keys = ["name", "city", "job", "preference", "habit", "goal"]
            profile_parts = []
            for k in profile_keys:
                v = get_profile(k)
                if v:
                    profile_parts.append(f"{k}: {v}")
            if profile_parts:
                parts.append("【用户画像】\n" + "\n".join(profile_parts))
        except Exception:
            # memory.py 不可用时静默跳过
            pass

        return "\n\n".join(parts) if parts else ""

    # ----------------------------------------------------------------
    # 短期记忆管理（当前对话上下文）
    # ----------------------------------------------------------------
    def add_short_term(self, content, metadata=None):
        """仅添加到短期记忆（不持久化），用于当前对话上下文"""
        if not content:
            return
        self._short_term.append({
            "id": str(uuid.uuid4()),
            "content": content,
            "metadata": metadata or {},
        })

    def get_short_term(self) -> list:
        """获取当前对话的短期记忆列表"""
        return list(self._short_term)

    def clear_short_term(self):
        """清空短期记忆（通常在新对话开始时调用）"""
        self._short_term.clear()


# ====================================================================
# 模块导出
# ====================================================================

__all__ = ["EnhancedMemory"]
