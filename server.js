require('dotenv').config();
const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const Database = require('better-sqlite3');

const app = express();
const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-this-in-production';
const DB_FILE = path.join(__dirname, 'data', 'database.sqlite');

// 占位导出对象，供路由模块同步 require；真实函数/值在 initDB() 后覆盖
const _exports = {};
Object.defineProperty(_exports, 'db', {
  get() { return db; },
  set(v) { db = v; },
  enumerable: true,
  configurable: true,
});
Object.assign(_exports, {
  signToken: () => {},
  verifyToken: () => {},
  authRequired: () => {},
  authLimiter: () => {},
  getApiKey: () => {},
  MODEL_CONFIG: {},
});
module.exports = _exports;

// ============================================================
// 安全中间件
// ============================================================
app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: '50mb' }));
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
  next();
});

// ============================================================
// 静态文件
// ============================================================
const staticDir = path.join(__dirname, 'public');
app.use(express.static(staticDir));
app.use('/uploads', express.static(path.join(staticDir, 'uploads')));

// ============================================================
// 限流中间件
// ============================================================
const requestCounts = new Map();
const RATE_LIMIT_WINDOW = 60000;
const RATE_LIMIT_MAX = 60;

function rateLimit(req, res, next) {
  const ip = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
  const now = Date.now();
  const record = requestCounts.get(ip) || { count: 0, resetTime: now + RATE_LIMIT_WINDOW };
  if (now > record.resetTime) { record.count = 0; record.resetTime = now + RATE_LIMIT_WINDOW; }
  record.count++;
  requestCounts.set(ip, record);
  if (record.count > RATE_LIMIT_MAX) return res.status(429).json({ error: '请求过于频繁，请稍后再试' });
  next();
}
app.use(rateLimit);

// ============================================================
// 数据库初始化
// ============================================================
let db = null;

function initDB() {
  fs.mkdirSync(path.dirname(DB_FILE), { recursive: true });
  db = new Database(DB_FILE);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE,
      password TEXT NOT NULL,
      credits INTEGER DEFAULT 0,
      role TEXT DEFAULT 'user',
      ref_code TEXT,
      referrer TEXT,
      register_ip TEXT,
      phone TEXT,
      device_fp TEXT,
      security_q TEXT,
      security_a TEXT,
      membership TEXT DEFAULT 'free',
      membership_expires TEXT,
      daily_free_usage INTEGER DEFAULT 0,
      daily_free_date TEXT,
      checkin_date TEXT,
      checkin_streak INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS api_keys (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      key_name TEXT,
      api_key TEXT UNIQUE NOT NULL,
      quota INTEGER DEFAULT 0,
      used INTEGER DEFAULT 0,
      active INTEGER DEFAULT 1,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS credit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      amount INTEGER NOT NULL,
      reason TEXT,
      admin TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS key_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      platform TEXT NOT NULL,
      prefix TEXT NOT NULL,
      models TEXT DEFAULT '[]',
      manage_url TEXT,
      notes TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS novels (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      title TEXT NOT NULL,
      type TEXT,
      outline TEXT,
      core TEXT,
      total_words INTEGER DEFAULT 0,
      chapter_count INTEGER DEFAULT 0,
      status TEXT DEFAULT 'draft',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS novel_characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      novel_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      gender TEXT,
      age TEXT,
      appearance TEXT,
      personality TEXT,
      background TEXT,
      goal TEXT,
      arc TEXT,
      notes TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS novel_worlds (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      novel_id INTEGER NOT NULL,
      category TEXT,
      key TEXT,
      value TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS novel_chapters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      novel_id INTEGER NOT NULL,
      chapter_index INTEGER DEFAULT 0,
      title TEXT,
      content TEXT,
      outline TEXT,
      word_count INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS novel_chapter_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      chapter_id INTEGER NOT NULL,
      username TEXT NOT NULL,
      version INTEGER DEFAULT 1,
      content TEXT,
      summary TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS knowledge_base (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      content TEXT NOT NULL,
      category TEXT DEFAULT 'general',
      tags TEXT,
      source TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS sync_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      data TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS plugins (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      version TEXT,
      description TEXT,
      author TEXT,
      enabled INTEGER DEFAULT 1,
      config TEXT DEFAULT '{}',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  db.exec(`
    CREATE TABLE IF NOT EXISTS manga (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      author TEXT,
      description TEXT,
      cover TEXT,
      status TEXT DEFAULT 'ongoing',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);
  const adminExists = db.prepare("SELECT id FROM users WHERE username='admin'").get();
  if (!adminExists) {
    const adminPwd = process.env.ADMIN_PASSWORD || 'admin123';
    db.prepare("INSERT INTO users (username, email, password, credits, role) VALUES (?,?,?,?,?)").run(
      'admin', 'admin@nexus-hub.local', bcrypt.hashSync(adminPwd, 10), 99999, 'admin');
  }
}

// ============================================================
// JWT 辅助函数
// ============================================================
function signToken(payload) {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '7d' });
}

function verifyToken(token) {
  return jwt.verify(token, JWT_SECRET);
}

// 仅允许健康检查的路径（不验证API Key）
const HEALTH_PATHS = ['/health', '/manifest.json', '/sw.js'];

function authRequired(req, res, next) {
  // 排除健康检查路径
  if (HEALTH_PATHS.includes(req.path)) return next();
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ ok: false, error: '请先登录' });
  }
  try {
    const payload = verifyToken(auth.slice(7));
    req.user = payload;
    next();
  } catch (e) {
    return res.status(401).json({ ok: false, error: '登录已过期，请重新登录' });
  }
}

const authLimiter = (req, res, next) => {
  const ip = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
  const now = Date.now();
  const record = requestCounts.get(ip) || { count: 0, resetTime: now + RATE_LIMIT_WINDOW };
  if (now > record.resetTime) { record.count = 0; record.resetTime = now + RATE_LIMIT_WINDOW; }
  record.count++;
  requestCounts.set(ip, record);
  if (record.count > 10) return res.status(429).json({ error: '请求过于频繁，请稍后再试' });
  next();
};

// ============================================================
// 模型配置
// ============================================================
const MODEL_CONFIG = {
  gpt4o: { provider: 'openai', model: 'gpt-4o', baseUrl: 'https://api.openai.com/v1' },
  gpt4turbo: { provider: 'openai', model: 'gpt-4-turbo', baseUrl: 'https://api.openai.com/v1' },
  claude35: { provider: 'openai', model: 'claude-3-5-sonnet-20241022', baseUrl: 'https://api.anthropic.com/v1' },
  claude3opus: { provider: 'openai', model: 'claude-3-opus-20240229', baseUrl: 'https://api.anthropic.com/v1' },
  gemini15pro: { provider: 'gemini', model: 'gemini-1.5-pro-latest' },
  gemini15flash: { provider: 'gemini', model: 'gemini-1.5-flash-latest' },
  deepseekv3: { provider: 'openai', model: 'deepseek-chat', baseUrl: 'https://api.deepseek.com/v1' },
  deepseekr1: { provider: 'openai', model: 'deepseek-reasoner', baseUrl: 'https://api.deepseek.com/v1' },
  glm4: { provider: 'openai', model: 'glm-4', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  glm4plus: { provider: 'openai', model: 'glm-4-plus', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  kimi: { provider: 'openai', model: 'moonshot-v1-8k', baseUrl: 'https://api.moonshot.cn/v1' },
  minimax: { provider: 'openai', model: 'abab6.5-chat', baseUrl: 'https://api.minimax.chat/v1' },
  spark4: { provider: 'openai', model: '4.0Ultra', baseUrl: 'https://spark-api-open.xf-yun.com/v1' },
  hunyuan: { provider: 'openai', model: 'hunyuan-pro', baseUrl: 'https://hunyuan.tencentcloudapi.com/v1' },
  qwen3: { provider: 'openai', model: 'qwen3-72b', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  qwen3max: { provider: 'openai', model: 'qwen3-72b', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  doubao: { provider: 'openai', model: 'doubao-pro-32k', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  doubao15: { provider: 'openai', model: 'doubao-1.5-pro-32k', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  gpt4omini: { provider: 'openai', model: 'gpt-4o-mini', baseUrl: 'https://api.openai.com/v1' },
  gemini25flash: { provider: 'gemini', model: 'gemini-2.5-flash-preview-04-21' },
  gemini25pro: { provider: 'gemini', model: 'gemini-2.5-pro-preview-03-25' },
  grok3: { provider: 'openai', model: 'grok-3', baseUrl: 'https://api.x.ai/v1' },
  mistral_large2: { provider: 'openai', model: 'mistral-large-latest', baseUrl: 'https://api.mistral.ai/v1' },
  llama4: { provider: 'openai', model: 'meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8', baseUrl: 'https://api.siliconflow.cn/v1' },
  ali_qwen36_flash: { provider: 'openai', model: 'qwen3-72b', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_qwen36_plus: { provider: 'openai', model: 'qwen3-235b-a22b', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_deepseek_v4_flash: { provider: 'openai', model: 'deepseek-v3', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_deepseek_v4_pro: { provider: 'openai', model: 'deepseek-r1', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_qwen37_max: { provider: 'openai', model: 'qwen-max-2025-01-25', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_kimi_k26: { provider: 'openai', model: 'kimi-k2.5', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_glm51: { provider: 'openai', model: 'glm-4.5', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  sf_qwen3_8b: { provider: 'openai', model: 'Qwen/Qwen3-8B', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_qwen3_32b: { provider: 'openai', model: 'Qwen/Qwen3-32B', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_deepseek_v3_free: { provider: 'openai', model: 'deepseek-ai/DeepSeek-V3', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_deepseek_v32: { provider: 'openai', model: 'deepseek-ai/DeepSeek-V3-0324', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_glm47: { provider: 'openai', model: 'THUDM/glm-4-9b-chat', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_glm5: { provider: 'openai', model: 'THUDM/GLM-4-9B-Chat', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_hunyuan_a13b: { provider: 'openai', model: 'tencent/Hunyuan-A13B-Instruct', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_qwen35_397b: { provider: 'openai', model: 'Qwen/Qwen3-235B-A22B', baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_qwq_32b: { provider: 'openai', model: 'Qwen/QwQ-32B', baseUrl: 'https://api.siliconflow.cn/v1' },
  bc_baichuan4: { provider: 'openai', model: 'Baichuan4', baseUrl: 'https://api.baichuan-ai.com/v1' },
  bc_baichuan3: { provider: 'openai', model: 'Baichuan3-Turbo', baseUrl: 'https://api.baichuan-ai.com/v1' },
  kimi2: { provider: 'openai', model: 'kimi-k2', baseUrl: 'https://api.moonshot.cn/v1' },
  minimax1: { provider: 'openai', model: 'MiniMax-Text-01', baseUrl: 'https://api.minimax.chat/v1' },
  or_codeqwen: { provider: 'openai', model: 'openrouter/qwen/coder', baseUrl: 'https://openrouter.ai/api/v1' },
  dmx_qwen35_2b_free: { provider: 'openai', model: 'qwen2.5-2b-instruct', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen3_17b_free: { provider: 'openai', model: 'qwen3-17b-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_spark_lite_free: { provider: 'openai', model: 'spark-lite', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen3_8b_free: { provider: 'openai', model: 'qwen3-8b-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen_flash_free: { provider: 'openai', model: 'qwen2.5-7b-instruct', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_minimax_m25_free: { provider: 'openai', model: 'minimax-m1-25k', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_47_free: { provider: 'openai', model: 'glm-4-9b-chat', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_47_flash: { provider: 'openai', model: 'glm-4-flash', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_45_flash: { provider: 'openai', model: 'glm-4-5-flash', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_4_9b: { provider: 'openai', model: 'glm-4-9b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_hunyuan_lite: { provider: 'openai', model: 'hunyuan-lite', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen35_plus_free: { provider: 'openai', model: 'qwen2.5-14b-instruct', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen3_5_plus_free: { provider: 'openai', model: 'qwen3-5-14b-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen35_35b_free: { provider: 'openai', model: 'qwen2.5-32b-instruct', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen25_coder_7b: { provider: 'openai', model: 'qwen2.5-coder-7b-instruct', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_doubao_seed_lite: { provider: 'openai', model: 'doubao-seed-lite-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_mimo_v25_free: { provider: 'openai', model: 'mimo-v2.5-7b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_minimax_m27_free: { provider: 'openai', model: 'minimax-m1-27k', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_5_turbo_free: { provider: 'openai', model: 'glm-5-turbo', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen3_coder_plus_free: { provider: 'openai', model: 'qwen3-coder-plus-14b-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen3_coder_next_free: { provider: 'openai', model: 'qwen3-coder-next-14b-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_doubao_seed_code: { provider: 'openai', model: 'doubao-seed-code-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_mimo_v2_pro_free: { provider: 'openai', model: 'mimo-v2-pro-7b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_code_free: { provider: 'openai', model: 'code-free-7b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_codex_free: { provider: 'openai', model: 'codex-free-7b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_kat_coder_free: { provider: 'openai', model: 'kat-coder-free-7b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen36_plus_free: { provider: 'openai', model: 'qwen3-72b-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_code_free_x: { provider: 'openai', model: 'code-free-x-7b', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_qwen3_max_free: { provider: 'openai', model: 'qwen3-max-2507', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_5_free: { provider: 'openai', model: 'glm-5-free', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  dmx_glm_51_free: { provider: 'openai', model: 'glm-5.1-free', baseUrl: 'https://api.lingyiwanwu.com/v1' },
  ark_dbs2_mini: { provider: 'openai', model: 'doubao-seed-1.5-lite-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbp15l: { provider: 'openai', model: 'doubao-pro-1.5-lite-32k-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs2_lite: { provider: 'openai', model: 'doubao-seed-1.5-lite-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dsv4f: { provider: 'openai', model: 'deepseek-v4-flash-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs1_6: { provider: 'openai', model: 'doubao-seed-1.6-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs1_8: { provider: 'openai', model: 'doubao-seed-1.8-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs_code: { provider: 'openai', model: 'doubao-seed-code-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dsv32: { provider: 'openai', model: 'deepseek-v3-0324', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dsv4p: { provider: 'openai', model: 'deepseek-v4-pro-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs2_pro: { provider: 'openai', model: 'doubao-seed-2.0-pro-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_glm47: { provider: 'openai', model: 'glm-4.7-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbp15p: { provider: 'openai', model: 'doubao-pro-1.5-pro-32k-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs_char: { provider: 'openai', model: 'doubao-seed-char-2507', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_doubao_pro: { provider: 'openai', model: 'doubao-pro-32k', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_doubao_lite: { provider: 'openai', model: 'doubao-lite-32k', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  nx_gpt5: { provider: 'nexus', model: 'gpt-5', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt5mini: { provider: 'nexus', model: 'gpt-5-mini', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt5chat: { provider: 'nexus', model: 'gpt-5-chat', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt5nano: { provider: 'nexus', model: 'gpt-5-nano', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt5all: { provider: 'nexus', model: 'gpt-5-all', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt51chat: { provider: 'nexus', model: 'gpt-5.1-chat', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt51codex: { provider: 'nexus', model: 'gpt-5.1-codex', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt51codexmax: { provider: 'nexus', model: 'gpt-5.1-codex-max', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt52chat: { provider: 'nexus', model: 'gpt-5.2-chat', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt52pro: { provider: 'nexus', model: 'gpt-5.2-pro', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt53chat: { provider: 'nexus', model: 'gpt-5.3-chat', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt53codex: { provider: 'nexus', model: 'gpt-5.3-codex', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt54pro: { provider: 'nexus', model: 'gpt-5.4-pro', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt54mini: { provider: 'nexus', model: 'gpt-5.4-mini', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt54nano: { provider: 'nexus', model: 'gpt-5.4-nano', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt55pro: { provider: 'nexus', model: 'gpt-5.5-pro', baseUrl: 'https://api.nexus.com/v1' },
  nx_gpt55: { provider: 'nexus', model: 'gpt-5.5', baseUrl: 'https://api.nexus.com/v1' },
  nx_claude_opus: { provider: 'nexus', model: 'claude-opus-4-20250514', baseUrl: 'https://api.nexus.com/v1' },
  nx_claude_sonnet: { provider: 'nexus', model: 'claude-sonnet-4-20250514', baseUrl: 'https://api.nexus.com/v1' },
  nx_claude_haiku: { provider: 'nexus', model: 'claude-haiku-4-20250514', baseUrl: 'https://api.nexus.com/v1' },
  nx_gemini_pro: { provider: 'nexus', model: 'gemini-2.5-pro-preview-03-25', baseUrl: 'https://api.nexus.com/v1' },
  nx_o3mini: { provider: 'nexus', model: 'o3-mini', baseUrl: 'https://api.nexus.com/v1' },
  nx_dalle3: { provider: 'nexus', model: 'dall-e-3', baseUrl: 'https://api.nexus.com/v1' },
  nx_flux: { provider: 'nexus', model: 'flux-pro', baseUrl: 'https://api.nexus.com/v1' },
  nx_suno: { provider: 'nexus', model: 'suno-v3', baseUrl: 'https://api.nexus.com/v1' },
  nx_grok3: { provider: 'nexus', model: 'grok-3', baseUrl: 'https://api.nexus.com/v1' },
  meshy_text: { provider: 'meshy', model: 'text-to-3d' },
  meshy_image: { provider: 'meshy', model: 'image-to-3d' },
  qiniu_claude37: { provider: 'openai', model: 'claude-3-7-sonnet-20250219', baseUrl: 'https://api.qiniu.com/v1' },
  qiniu_claudeopus4: { provider: 'openai', model: 'claude-opus-4-20250514', baseUrl: 'https://api.qiniu.com/v1' },
  qiniu_gpt4o: { provider: 'openai', model: 'gpt-4o-2024-11-20', baseUrl: 'https://api.qiniu.com/v1' },
  qiniu_o3: { provider: 'openai', model: 'o3-2025-04-16', baseUrl: 'https://api.qiniu.com/v1' },
  qiniu_gemini25pro: { provider: 'openai', model: 'gemini-2.5-pro-preview-03-25', baseUrl: 'https://api.qiniu.com/v1' },
  claude4: { provider: 'openai', model: 'claude-4-sonnet-20250514', baseUrl: 'https://api.anthropic.com/v1' },
  claude4opus: { provider: 'openai', model: 'claude-4-opus-20250514', baseUrl: 'https://api.anthropic.com/v1' },
  or_llama3_70b: { provider: 'openai', model: 'meta-llama/llama-3-70b-instruct', baseUrl: 'https://openrouter.ai/api/v1' },
  or_mistral_large: { provider: 'openai', model: 'mistralai/mistral-large', baseUrl: 'https://openrouter.ai/api/v1' },
  or_perplexity: { provider: 'openai', model: 'perplexity/sonar', baseUrl: 'https://openrouter.ai/api/v1' },
  or_gpt4o: { provider: 'openai', model: 'openai/gpt-4o', baseUrl: 'https://openrouter.ai/api/v1' },
  or_claude_sonnet: { provider: 'openai', model: 'anthropic/claude-3.5-sonnet', baseUrl: 'https://openrouter.ai/api/v1' },
  or_gemini25pro: { provider: 'openai', model: 'google/gemini-2.5-pro-preview-03-25', baseUrl: 'https://openrouter.ai/api/v1' },
};

function getApiKey(provider, modelId) {
  switch (provider) {
    case 'openai':
      if (modelId.startsWith('dmx_')) return process.env.DMX_API_KEY;
      if (modelId.startsWith('ark_')) return process.env.ARK_API_KEY;
      if (modelId.startsWith('sf_')) return process.env.SILICONFLOW_API_KEY;
      if (modelId.startsWith('ali_')) return process.env.DASHSCOPE_API_KEY;
      if (modelId.startsWith('bc_')) return process.env.BAICHUAN_API_KEY;
      if (modelId.startsWith('or_')) return process.env.OPENROUTER_API_KEY;
      if (modelId.startsWith('qiniu_')) return process.env.QINIU_API_KEY;
      if (modelId === 'gpt4o' || modelId === 'gpt4turbo' || modelId === 'gpt4omini') return process.env.OPENAI_API_KEY;
      if (modelId.startsWith('claude') || modelId === 'claude4' || modelId === 'claude4opus') return process.env.ANTHROPIC_API_KEY;
      if (modelId.startsWith('gemini')) return process.env.GEMINI_API_KEY;
      if (modelId.startsWith('deepseek')) return process.env.DEEPSEEK_API_KEY;
      if (modelId.startsWith('glm')) return process.env.GLM_API_KEY;
      if (modelId.startsWith('kimi')) return process.env.MOONSHOT_API_KEY;
      if (modelId.startsWith('minimax')) return process.env.MINIMAX_API_KEY;
      if (modelId.startsWith('spark')) return process.env.SPARK_API_KEY;
      if (modelId.startsWith('hunyuan')) return process.env.HUNYUAN_API_KEY;
      if (modelId.startsWith('qwen')) return process.env.DASHSCOPE_API_KEY;
      if (modelId.startsWith('doubao')) return process.env.ARK_API_KEY;
      if (modelId.startsWith('grok')) return process.env.XAI_API_KEY;
      if (modelId.startsWith('mistral')) return process.env.MISTRAL_API_KEY;
      if (modelId.startsWith('llama')) return process.env.SILICONFLOW_API_KEY;
      return process.env.OPENAI_API_KEY;
    case 'gemini':
      return process.env.GEMINI_API_KEY;
    case 'qianfan':
      return 'qianfan';
    case 'nexus':
      return process.env.NEXUS_API_KEY;
    case 'meshy':
      return process.env.MESHY_API_KEY;
    default:
      return process.env.OPENAI_API_KEY;
  }
}

// ============================================================
// 密码辅助函数
// ============================================================
function btoaPwd(pwd) { return Buffer.from(pwd).toString('base64'); }
function isBcryptHash(hash) { return typeof hash === 'string' && (hash.startsWith('$2a$') || hash.startsWith('$2b$')); }
function hashPasswordSync(pwd) { return bcrypt.hashSync(pwd, 10); }
function verifyPasswordSync(pwd, storedHash) {
  if (isBcryptHash(storedHash)) return bcrypt.compareSync(pwd, storedHash);
  return storedHash === btoaPwd(pwd);
}
function upgradePasswordToBcrypt(username, plainPwd) {
  const newHash = hashPasswordSync(plainPwd);
  db.prepare("UPDATE users SET password=? WHERE username=?").run(newHash, username);
}

// ============================================================
// 同步初始化并启动
// ============================================================
initDB();

// 挂载路由模块
require('./routes/chat')(app);
require('./routes/models')(app);
require('./routes/media')(app, { staticDir });
require('./routes/auth')(app);
require('./routes/novel')(app);
require('./routes/knowledge')(app);
require('./routes/payment')(app);
require('./routes/openai_compat')(app);
require('./routes/guest')(app);
require('./routes/sync')(app);
require('./routes/plugins')(app);
require('./routes/manga')(app);

// SPA 路由
app.get('/', (req, res) => res.sendFile(path.join(staticDir, 'index.html')));
app.get('/dashboard', (req, res) => res.sendFile(path.join(staticDir, 'index.html')));
app.get('/app', (req, res) => res.sendFile(path.join(staticDir, 'index.html')));
app.get('/app/*', (req, res) => res.sendFile(path.join(staticDir, 'index.html')));

// 健康检查端点
app.get('/health', (req, res) => {
  const memUsage = process.memoryUsage();
  res.json({
    status: 'ok',
    uptime: Math.floor(process.uptime()),
    memory: {
      rss: Math.round(memUsage.rss / 1024 / 1024) + 'MB',
      heapUsed: Math.round(memUsage.heapUsed / 1024 / 1024) + 'MB'
    },
    database: db ? 'connected' : 'disconnected'
  });
});

// 404 / 500 处理
app.use((req, res) => res.status(404).json({ error: 'Not Found' }));
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: 'Internal Server Error' });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

// 覆盖初始占位导出（db 的 getter/setter 保留在 _exports 上，其余替换为真实实现）
Object.assign(_exports, {
  signToken,
  verifyToken,
  authRequired,
  authLimiter,
  getApiKey,
  MODEL_CONFIG,
});
