/**
 * Nexus Hub - 大模型聚合平台后端代理
 *
 * 统一代理多个 AI 模型提供商的 API，保护密钥安全。
 * 启动: npm start / npm run dev
 * 重启 (pm2): pm2 restart nexus-hub
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const jwt = require("jsonwebtoken");
// const rateLimit = require("express-rate-limit"); // CentOS 8/Node 14 不支持 node:buffer
const SALT_ROUNDS = 10;
// dotenv: 优先加载项目根目录 .env，兼容本地开发与服务器部署
require('dotenv').config({ path: path.join(__dirname, '.env') });
// 服务器部署时也尝试加载 /home/admin/.env（不覆盖已有变量）
if (process.platform === 'linux' && fs.existsSync('/home/admin/.env')) {
  require('dotenv').config({ path: '/home/admin/.env', override: false });
}
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');

const app = express();
app.use(cors({
  origin: ['https://j3trisheng.com', 'https://www.j3trisheng.com', 'http://localhost:3001', 'http://localhost'],
  credentials: true,
}));
app.use(morgan('short'));
app.use(express.json({ limit: '10mb' }));

// 提供前端静态文件（支持多种目录结构：本地开发 / Railway 部署）
let staticDir = path.resolve(__dirname, '..');
if (!fs.existsSync(path.join(staticDir, 'index.html')) && !fs.existsSync(path.join(staticDir, 'dashboard.html'))) {
  staticDir = __dirname; // 部署时文件可能在同目录
}
// JWT密钥 & 速率限制
const JWT_SECRET = process.env.JWT_SECRET || crypto.randomBytes(32).toString('hex');
if (!process.env.JWT_SECRET) {
  try {
    var ec = require('fs').readFileSync(require('path').join(__dirname, '.env'), 'utf8');
    if (!ec.includes('JWT_SECRET=')) {
      require('fs').appendFileSync(require('path').join(__dirname, '.env'), '\n# JWT密钥（自动生成，请勿泄露）\nJWT_SECRET=' + JWT_SECRET + '\n');
    }
  } catch(e) {}
}
// ============================================================
// 简单的内存速率限制（替代 express-rate-limit）
// ============================================================
const rateLimitStore = new Map();
function simpleRateLimit(windowMs, max) {
  return (req, res, next) => {
    const ip = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
    const now = Date.now();
    const key = ip + ':' + (req.originalUrl || req.url);
    let entry = rateLimitStore.get(key);
    if (!entry || now > entry.resetTime) {
      entry = { count: 0, resetTime: now + windowMs };
      rateLimitStore.set(key, entry);
    }
    entry.count++;
    if (entry.count > max) {
      return res.json({ ok: false, error: '请求过于频繁，请稍后再试' });
    }
    next();
  };
}
// 定时清理过期记录
setInterval(() => {
  const now = Date.now();
  for (const [key, val] of rateLimitStore) {
    if (now > val.resetTime) rateLimitStore.delete(key);
  }
}, 60000);

const authLimiter = simpleRateLimit(15*60*1000, 10);
function signToken(p) { return require('jsonwebtoken').sign(p, JWT_SECRET, { expiresIn:'7d' }); }
function verifyToken(t) { return require('jsonwebtoken').verify(t, JWT_SECRET); }
function authRequired(req,res,next) {
  if (!req.headers.authorization?.startsWith('Bearer ')) return res.status(401).json({ ok:false, error:'未登录' });
  try { req.user = verifyToken(req.headers.authorization.slice(7)); next(); }
  catch(e) { return res.status(401).json({ ok:false, error:'登录已过期，请重新登录' }); }
}

// 首页 - 落地页
app.get('/', (req, res) => {
  const landingPath = path.join(staticDir, 'landing.html');
  if (fs.existsSync(landingPath)) {
    res.sendFile(landingPath);
  } else {
    res.sendFile(path.join(staticDir, 'index.html'));
  }
});

// 控制台（原首页）
app.get('/dashboard', (req, res) => {
  const dashPath = path.join(staticDir, 'dashboard.html');
  if (fs.existsSync(dashPath)) {
    res.sendFile(dashPath);
  } else {
    res.sendFile(path.join(staticDir, 'index.html'));
  }
});

// 其他静态资源
app.use(express.static(staticDir));

// Nexus Studio 前端 PWA 静态文件服务
// 部署时前端文件位于 /home/admin/nexus-studio，可通过 /studio 访问
const studioDir = process.env.STUDIO_DIR || '/home/admin/nexus-studio';
if (fs.existsSync(studioDir)) {
  app.use('/studio', express.static(studioDir, {
    // 禁止缓存，防止 Service Worker 缓存旧版本导致 init is not defined 等错误
    setHeaders: function(res, filePath) {
      if (filePath.endsWith('.html') || filePath.endsWith('.js') || filePath.endsWith('.css') || filePath.endsWith('.json')) {
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.setHeader('Pragma', 'no-cache');
        res.setHeader('Expires', '0');
      }
    }
  }));
}

const PORT = process.env.PORT || 3001;

// ============================================================
// 百度千帆 Access Token 缓存
// ============================================================
let qianfanToken = null;
let qianfanTokenExpiry = 0;
async function getQianfanToken() {
  if (qianfanToken && Date.now() < qianfanTokenExpiry) return qianfanToken;
  try {
    const ak = process.env.QIANFAN_AK;
    const sk = process.env.QIANFAN_SK;
    if (!ak || !sk) return null;
    const r = await fetch(`https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=${ak}&client_secret=${sk}`);
    const d = await r.json();
    if (d.access_token) {
      qianfanToken = d.access_token;
      qianfanTokenExpiry = Date.now() + (d.expires_in - 300) * 1000;
      return qianfanToken;
    }
  } catch(e) { console.error('Qianfan token error:', e.message); }
  return null;
}

// ============================================================
// 模型到 API 配置的映射
// ============================================================
const MODEL_CONFIG = {
  gpt4o:        { provider: 'openai',   model: 'gpt-4o',             baseUrl: process.env.OPENAI_BASE_URL },
  gpt4omini:    { provider: 'openai',   model: 'gpt-4o-mini',        baseUrl: process.env.OPENAI_BASE_URL },
  deepseekv3:   { provider: 'openai',   model: 'deepseek-chat',      baseUrl: 'https://api.deepseek.com/v1' },
  deepseekr1:   { provider: 'openai',   model: 'deepseek-reasoner',  baseUrl: 'https://api.deepseek.com/v1' },
  gemini25pro:  { provider: 'nexus',   model: 'gemini-2.5-pro',             baseUrl: 'https://apinexus.net/v1' },
  gemini25flash:{ provider: 'openai',   model: 'google/gemini-2.5-flash',        baseUrl: 'https://openrouter.ai/api/v1' },
  qwen3:        { provider: 'openai',   model: 'qwen3-235b-a22b',    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  kimi2:        { provider: 'openai',   model: 'moonshot-v1-128k',   baseUrl: 'https://api.moonshot.cn/v1' },
  glm4plus:     { provider: 'openai',   model: 'glm-4-plus',         baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  hunyuan:      { provider: 'openai',   model: 'hunyuan-turbos-latest', baseUrl: 'https://api.hunyuan.cloud.tencent.com/v1' },

  // === 硅基流动 SiliconFlow ===
  sf_qwen3_8b:       { provider: 'openai', model: 'Qwen/Qwen3-8B',                 baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_deepseek_v3_free:{ provider: 'openai', model: 'deepseek-ai/DeepSeek-V3',       baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_deepseek_v32:   { provider: 'openai', model: 'deepseek-ai/DeepSeek-V3.2',      baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_glm5:          { provider: 'openai', model: 'Pro/zai-org/GLM-5',              baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_glm47:         { provider: 'openai', model: 'Pro/zai-org/GLM-4.7',            baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_qwen3_32b:     { provider: 'openai', model: 'Qwen/Qwen3-32B',                 baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_qwen35_397b:   { provider: 'openai', model: 'Qwen/Qwen3.5-397B-A17B',         baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_qwq_32b:       { provider: 'openai', model: 'Qwen/QwQ-32B',                   baseUrl: 'https://api.siliconflow.cn/v1' },
  sf_hunyuan_a13b:  { provider: 'openai', model: 'tencent/Hunyuan-A13B-Instruct',  baseUrl: 'https://api.siliconflow.cn/v1' },

  // === 阿里云百炼 ===
  ali_qwen37_max:        { provider: 'openai', model: 'qwen3.7-max',          baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_qwen36_plus:       { provider: 'openai', model: 'qwen3.6-plus',         baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_qwen36_flash:      { provider: 'openai', model: 'qwen3.6-flash',        baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_deepseek_v4_pro:   { provider: 'openai', model: 'deepseek-v4-pro',      baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_deepseek_v4_flash: { provider: 'openai', model: 'deepseek-v4-flash',    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_glm51:             { provider: 'openai', model: 'glm-5.1',              baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ali_kimi_k26:          { provider: 'openai', model: 'kimi-k2.6',            baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },

  // === DMXAPI ===
  dmx_minimax_m27_free:  { provider: 'openai', model: 'MiniMax-M2.7-free',         baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_minimax_m25_free:  { provider: 'openai', model: 'MiniMax-M2.5-free',         baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_47_free:       { provider: 'openai', model: 'glm-4.7-free',              baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_47_flash:      { provider: 'openai', model: 'glm-4.7-flash',             baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_5_free:        { provider: 'openai', model: 'glm-5-free',                baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_51_free:       { provider: 'openai', model: 'glm-5.1-free',              baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_5_turbo_free:  { provider: 'openai', model: 'glm-5-turbo-free',          baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_45_flash:      { provider: 'openai', model: 'GLM-4.5-Flash',             baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_glm_4_9b:          { provider: 'openai', model: 'THUDM/glm-4-9b-chat',        baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_hunyuan_lite:      { provider: 'openai', model: 'hunyuan-lite',              baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen3_8b_free:     { provider: 'openai', model: 'qwen3-8b-free',             baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen_flash_free:   { provider: 'openai', model: 'qwen-flash-free',           baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen3_5_plus_free: { provider: 'openai', model: 'qwen3-5-plus-free',         baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen35_plus_free:  { provider: 'openai', model: 'qwen3.5-plus-free',         baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen3_coder_plus_free:{ provider: 'openai', model: 'qwen3-coder-plus-free',  baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen3_coder_next_free:{ provider: 'openai', model: 'qwen3-coder-next-free',  baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen35_2b_free:    { provider: 'openai', model: 'Qwen3.5-2B-free',           baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen35_35b_free:   { provider: 'openai', model: 'Qwen3.5-35B-A3B-free',      baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen3_17b_free:    { provider: 'openai', model: 'Qwen3-1.7B-free',           baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen3_max_free:    { provider: 'openai', model: 'qwen3-max-2026-01-23-free', baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen25_coder_7b:   { provider: 'openai', model: 'Qwen/Qwen2.5-Coder-7B-Instruct', baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_kimi_k25_free:     { provider: 'openai', model: 'kimi-k2.5-free',            baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_kimi_k26_free:     { provider: 'openai', model: 'kimi-k2.6-free',            baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_doubao_seed_pro:   { provider: 'openai', model: 'doubao-seed-2.0-pro-free',  baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_doubao_seed_lite:  { provider: 'openai', model: 'doubao-seed-2.0-lite-free', baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_doubao_seed_code:  { provider: 'openai', model: 'doubao-seed-2.0-code-free', baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_spark_lite_free:   { provider: 'openai', model: 'spark-lite-free',           baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_mimo_v2_pro_free:  { provider: 'openai', model: 'mimo-v2-pro-free',          baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_mimo_v25_free:     { provider: 'openai', model: 'mimo-v2.5-free',            baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_code_free:         { provider: 'openai', model: 'DMXAPI-Code-Free',          baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_codex_free:        { provider: 'openai', model: 'DMXAPI-CodeX-Free',         baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_kat_coder_free:    { provider: 'openai', model: 'KAT-Coder-ProV2-free',      baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_qwen36_plus_free:  { provider: 'openai', model: 'qwen3.6-plus-free',         baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_code_free_x:       { provider: 'openai', model: 'DMXAPI-Code-Free-X',        baseUrl: 'https://www.dmxapi.cn/v1' },

  // === 百度千帆 ===
  qf_ernie4:         { provider: 'qianfan',  model: 'ernie-4.0-8k',             baseUrl: 'https://qianfan.baidubce.com/v2' },
  qf_ernie35:        { provider: 'qianfan',  model: 'ernie-3.5-8k',             baseUrl: 'https://qianfan.baidubce.com/v2' },
  qf_ernie_speed:    { provider: 'qianfan',  model: 'ernie-speed-128k',         baseUrl: 'https://qianfan.baidubce.com/v2' },

  // === 火山引擎 Ark（DeepSeek/豆包/GLM 全免费接入） ===
  ark_dsv32:          { provider: 'openai', model: 'ep-20260606020151-4qv8h',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dsv4f:          { provider: 'openai', model: 'ep-20260606020130-t75wz',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dsv4p:          { provider: 'openai', model: 'ep-20260606020111-9j75t',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs2_pro:       { provider: 'openai', model: 'ep-20260606015252-n6gdv',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs2_lite:      { provider: 'openai', model: 'ep-20260606015318-njb98',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs2_mini:      { provider: 'openai', model: 'ep-20260606015445-xdsmx',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs_code:       { provider: 'openai', model: 'ep-20260606015514-hbm6v',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs1_8:         { provider: 'openai', model: 'ep-20260606015615-m4fdz',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs_char:       { provider: 'openai', model: 'ep-20260606015638-qqfjr',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_doubao_pro:     { provider: 'openai', model: 'doubao-pro',              baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_doubao_lite:    { provider: 'openai', model: 'doubao-lite',             baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbs1_6:         { provider: 'openai', model: 'ep-20260606015941-mtwc2',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbp15p:         { provider: 'openai', model: 'ep-20260606014616-t79qr',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_dbp15l:         { provider: 'openai', model: 'ep-20260606014948-p49s2',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  ark_glm47:          { provider: 'openai', model: 'ep-20260606020254-wr4km',  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },

  // === API Nexus (海外旗舰模型) ===
  nx_gpt5:            { provider: 'nexus', model: 'gpt-5-pro',              baseUrl: 'https://apinexus.net/v1' },
  nx_gpt5mini:        { provider: 'nexus', model: 'gpt-5-mini',             baseUrl: 'https://apinexus.net/v1' },
  nx_gpt5chat:        { provider: 'nexus', model: 'gpt-5-chat',            baseUrl: 'https://apinexus.net/v1' },
  nx_gpt5nano:        { provider: 'nexus', model: 'gpt-5-nano',            baseUrl: 'https://apinexus.net/v1' },
  nx_gpt5all:         { provider: 'nexus', model: 'gpt-5-all',             baseUrl: 'https://apinexus.net/v1' },
  nx_gpt51chat:       { provider: 'nexus', model: 'gpt-5.1-chat',          baseUrl: 'https://apinexus.net/v1' },
  nx_gpt51codex:      { provider: 'nexus', model: 'gpt-5.1-codex',         baseUrl: 'https://apinexus.net/v1' },
  nx_gpt51codexmax:   { provider: 'nexus', model: 'gpt-5.1-codex-max',     baseUrl: 'https://apinexus.net/v1' },
  nx_gpt52chat:       { provider: 'nexus', model: 'gpt-5.2-chat-2025-12-11', baseUrl: 'https://apinexus.net/v1' },
  nx_gpt52pro:        { provider: 'nexus', model: 'gpt-5.2-pro-2025-12-11',  baseUrl: 'https://apinexus.net/v1' },
  nx_gpt53chat:       { provider: 'nexus', model: 'gpt-5.3-chat-latest',   baseUrl: 'https://apinexus.net/v1' },
  nx_gpt53codex:      { provider: 'nexus', model: 'gpt-5.3-codex-latest',  baseUrl: 'https://apinexus.net/v1' },
  nx_gpt54pro:        { provider: 'nexus', model: 'gpt-5.4-pro-2026-03-05',   baseUrl: 'https://apinexus.net/v1' },
  nx_gpt54mini:       { provider: 'nexus', model: 'gpt-5.4-mini-2026-03-17',  baseUrl: 'https://apinexus.net/v1' },
  nx_gpt54nano:       { provider: 'nexus', model: 'gpt-5.4-nano-2026-03-17',  baseUrl: 'https://apinexus.net/v1' },
  nx_gpt55pro:        { provider: 'nexus', model: 'gpt-5.5-pro-2026-04-23',   baseUrl: 'https://apinexus.net/v1' },
  nx_gpt55:           { provider: 'nexus', model: 'gpt-5.5-2026-04-24',    baseUrl: 'https://apinexus.net/v1' },
  nx_claude_opus:     { provider: 'nexus', model: 'claude-opus-4-6',        baseUrl: 'https://apinexus.net/v1' },
  nx_claude_sonnet:   { provider: 'nexus', model: 'claude-sonnet-4-6',      baseUrl: 'https://apinexus.net/v1' },
  nx_claude_haiku:    { provider: 'nexus', model: 'claude-haiku-4-5',       baseUrl: 'https://apinexus.net/v1' },
  nx_gemini_pro:      { provider: 'nexus', model: 'gemini-2.5-pro',         baseUrl: 'https://apinexus.net/v1' },
  nx_o3mini:          { provider: 'nexus', model: 'o3-mini',                baseUrl: 'https://apinexus.net/v1' },
  nx_dalle3:          { provider: 'nexus', model: 'dall-e-3',               baseUrl: 'https://apinexus.net/v1' },
  nx_flux:            { provider: 'nexus', model: 'flux-pro',               baseUrl: 'https://apinexus.net/v1' },
  nx_suno:            { provider: 'nexus', model: 'suno-v5',                baseUrl: 'https://apinexus.net/v1' },
  nx_grok3:           { provider: 'nexus', model: 'grok-3',                 baseUrl: 'https://apinexus.net/v1' },
  bc_baichuan4:      { provider: 'openai',   model: 'Baichuan4',                baseUrl: 'https://api.baichuan-ai.com/v1' },
  bc_baichuan3:      { provider: 'openai',   model: 'Baichuan3-Turbo',          baseUrl: 'https://api.baichuan-ai.com/v1' },

  // === 七牛云合规 ===
  qiniu_claude37:     { provider: 'openai', model: 'claude-3-7-sonnet-20250219',  baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_claudeopus4:  { provider: 'openai', model: 'claude-opus-4-20250514',      baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_gpt4o:        { provider: 'openai', model: 'gpt-4o',                      baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_o3:           { provider: 'openai', model: 'o3',                          baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_gemini25pro:  { provider: 'openai', model: 'gemini-2.5-pro',              baseUrl: 'https://api.qnaiqc.com/v1' },

  // === OpenRouter ===
  or_gpt4o:          { provider: 'openai', model: 'openai/gpt-4o',              baseUrl: 'https://openrouter.ai/api/v1' },
  or_claude_sonnet:  { provider: 'openai', model: 'anthropic/claude-4-sonnet-20250514', baseUrl: 'https://openrouter.ai/api/v1' },
  or_gemini25pro:    { provider: 'openai', model: 'google/gemini-2.5-pro',           baseUrl: 'https://openrouter.ai/api/v1' },
  or_llama3_70b:     { provider: 'openai', model: 'meta-llama/llama-3-70b-instruct', baseUrl: 'https://openrouter.ai/api/v1' },
  or_mistral_large:  { provider: 'openai', model: 'mistralai/mistral-large',    baseUrl: 'https://openrouter.ai/api/v1' },
  or_perplexity:     { provider: 'openai', model: 'perplexity/llama-3.1-sonar-huge-128k-online', baseUrl: 'https://openrouter.ai/api/v1' },
  or_codeqwen:       { provider: 'openai', model: 'qwen/qwen-2.5-coder-32b-instruct', baseUrl: 'https://openrouter.ai/api/v1' },
  // 前端展示的海外模型路由
  claude4:           { provider: 'openai', model: 'anthropic/claude-4-sonnet-20250514',  baseUrl: 'https://openrouter.ai/api/v1' },
  claude4opus:       { provider: 'openai', model: 'anthropic/claude-opus-4-20250514',    baseUrl: 'https://openrouter.ai/api/v1' },
  llama4:            { provider: 'openai', model: 'meta-llama/llama-4-scout',            baseUrl: 'https://openrouter.ai/api/v1' },
  'mistral-large2': { provider: 'openai', model: 'mistralai/mistral-large-2',           baseUrl: 'https://openrouter.ai/api/v1' },
  grok3:             { provider: 'openai', model: 'x-ai/grok-3',                         baseUrl: 'https://openrouter.ai/api/v1' },
  // 豆包/MiniMax via DMXAPI
  doubao15:          { provider: 'openai', model: 'doubao-seed-2.0-pro-free',            baseUrl: 'https://www.dmxapi.cn/v1' },
  minimax1:          { provider: 'openai', model: 'MiniMax-M2.7-free',                   baseUrl: 'https://www.dmxapi.cn/v1' },

  // === 旧模型 ID 补充接入 ===
  gpt4turbo:    { provider: 'openai', model: 'gpt-4-turbo',                baseUrl: process.env.OPENAI_BASE_URL },
  claude35:     { provider: 'openai', model: 'anthropic/claude-3-sonnet',   baseUrl: 'https://openrouter.ai/api/v1' },
  claude3opus:  { provider: 'openai', model: 'anthropic/claude-3-opus',    baseUrl: 'https://openrouter.ai/api/v1' },
  gemini15pro:  { provider: 'openai', model: 'google/gemini-1.5-pro',      baseUrl: 'https://openrouter.ai/api/v1' },
  gemini15flash:{ provider: 'openai', model: 'google/gemini-1.5-flash',    baseUrl: 'https://openrouter.ai/api/v1' },
  kimi:         { provider: 'openai', model: 'moonshot-v1-8k',             baseUrl: 'https://api.moonshot.cn/v1' },
  glm4:         { provider: 'openai', model: 'glm-4',                      baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  minimax:      { provider: 'openai', model: 'MiniMax-M2.7-free',          baseUrl: 'https://www.dmxapi.cn/v1' },
  doubao:       { provider: 'openai', model: 'doubao-seed-2.0-pro-free',   baseUrl: 'https://www.dmxapi.cn/v1' },
  spark4:       { provider: 'openai', model: 'spark-lite-free',            baseUrl: 'https://www.dmxapi.cn/v1' },
};

// 接入状态说明：gpt4turbo/claude35/claude3opus/gemini15pro/gemini15flash/kimi/glm4/minimax/doubao/spark4 已通过对应渠道接入

// ============================================================
// API Key 管理
// ============================================================
function getApiKey(provider, modelId) {
  // 百度千帆 (专用token)
  if (modelId.startsWith('qf_') || provider === 'qianfan') return 'qianfan'; // 标记，实际token从getQianfanToken()获取
  // 火山引擎
  if (modelId.startsWith('ark_'))    return process.env.ARK_API_KEY;
  // 百川智能
  if (modelId.startsWith('bc_'))     return process.env.BAICHUAN_API_KEY;
  // API Nexus（无论模型ID，provider=nexus 的都用这个 key）
  if (modelId.startsWith('nx_') || provider === 'nexus') return process.env.NEXUS_API_KEY;
  // DeepSeek 使用自己的 key
  if (modelId.startsWith('deepseek')) return process.env.DEEPSEEK_API_KEY;
  if (modelId.startsWith('qwen'))     return process.env.DASHSCOPE_API_KEY;
  if (modelId.startsWith('kimi'))     return process.env.MOONSHOT_API_KEY;
  if (modelId.startsWith('glm'))      return process.env.ZHIPU_API_KEY;
  if (modelId.startsWith('hunyuan'))  return process.env.HUNYUAN_API_KEY;
  if (modelId.startsWith('sf_'))     return process.env.SILICONFLOW_API_KEY;
  if (modelId.startsWith('ali_'))    return process.env.DASHSCOPE_API_KEY;  // 百炼共用阿里云Key
  if (modelId.startsWith('dmx_'))    return process.env.DMXAPI_API_KEY;
  if (modelId.startsWith('or_'))     return process.env.OPENROUTER_API_KEY;
  if (modelId.startsWith('qiniu_'))  return process.env.QINIU_API_KEY;
  if (modelId.startsWith('claude'))   return process.env.OPENROUTER_API_KEY;
  if (modelId.startsWith('gemini25')) return process.env.OPENROUTER_API_KEY;
  if (modelId.startsWith('gemini15')) return process.env.OPENROUTER_API_KEY;
  if (modelId.startsWith('llama'))    return process.env.OPENROUTER_API_KEY;
  if (modelId.startsWith('mistral'))  return process.env.OPENROUTER_API_KEY;
  if (modelId.startsWith('grok'))     return process.env.OPENROUTER_API_KEY;

  switch (provider) {
    case 'openai':  return process.env.OPENAI_API_KEY;
    case 'gemini':  return process.env.GEMINI_API_KEY;
    default:        return null;
  }
}

// ============================================================
// OpenAI 兼容格式请求 (DeepSeek, Qwen, Kimi, GLM, Yi 等都走这里)
// ============================================================
async function callOpenAICompatible(config, messages, apiKey) {
  const url = `${config.baseUrl}/chat/completions`;

  const body = JSON.stringify({
    model: config.model,
    messages: messages,
    temperature: 0.7,
    max_tokens: 4096,
  });

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body,
  });

  if (!res.ok) {
    const err = await res.text();
    console.log(`[API ERROR] ${config.model} → ${res.status}: ${err.substring(0,200)}`);
    throw new Error(`API 调用失败 [${res.status}]: ${err}`);
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content;
  if (!content) {
    console.log(`[EMPTY] ${config.model} 返回空内容, response keys:`, Object.keys(data).join(','));
    throw new Error('模型返回了空内容，可能不是文本对话模型或请求格式有误');
  }
  return content;
}

// ============================================================
// Google Gemini 请求 (使用 REST API，避免 SDK 兼容问题)
// ============================================================
async function callGemini(config, messages, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${config.model}:generateContent?key=${apiKey}`;

  // 转换消息格式为 Gemini API 格式
  const contents = [];
  let systemInstruction = '';

  for (const msg of messages) {
    if (msg.role === 'system') {
      systemInstruction = msg.content;
    } else if (msg.role === 'user') {
      contents.push({ role: 'user', parts: [{ text: msg.content }] });
    } else if (msg.role === 'assistant') {
      contents.push({ role: 'model', parts: [{ text: msg.content }] });
    }
  }

  const body = { contents };
  if (systemInstruction) {
    body.systemInstruction = { parts: [{ text: systemInstruction }] };
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini API 调用失败 [${res.status}]: ${err}`);
  }

  const data = await res.json();
  return data.candidates?.[0]?.content?.parts?.[0]?.text || '(Gemini 返回为空)';
}

// ============================================================
// IP 速率限制（防API直调绕过前端积分检查）
// ============================================================
const ipRateMap = new Map(); // IP → {count, resetTime}
const IP_FREE_LIMIT = 20;    // 每个IP每日免费调用次数
const IP_RATE_WINDOW = 60000; // 速率窗口 1分钟
const IP_RATE_MAX = 30;       // 每分钟最多30次

function checkIpRate(ip, modelId) {
  const now = Date.now();
  // 高成本模型判断：API Nexus / 海外旗舰
  const isHighCost = modelId.startsWith('nx_') || modelId.startsWith('or_') || modelId.startsWith('qiniu_') || 
    ['gpt4o','deepseekr1','claude4','claude4opus','gemini25pro','grok3'].includes(modelId);
  // 免费模型：DMXAPI、硅基、火山引擎
  const isFree = modelId.startsWith('dmx_') || modelId.startsWith('ark_') || 
    ['sf_qwen3_8b','sf_deepseek_v3_free','sf_qwen3_32b','sf_glm47','qf_ernie_speed'].includes(modelId);
  
  // 免费模型不限
  if (isFree) return { blocked: false };
  
  // 清理过期记录
  for (const [key, val] of ipRateMap) {
    if (now > val.resetTime) ipRateMap.delete(key);
  }
  
  let record = ipRateMap.get(ip);
  if (!record || now > record.dailyReset) {
    record = { count: 0, dailyCount: 0, dailyReset: now + 86400000, resetTime: now + IP_RATE_WINDOW };
    ipRateMap.set(ip, record);
  }
  
  record.count++;
  record.dailyCount++;
  
  // 每分钟速度限制
  if (record.count > IP_RATE_MAX) return { blocked: true, reason: `请求过频（${IP_RATE_MAX}次/分钟），请稍后重试` };
  
  // 高成本模型 + 无API Key → 限制每日次数
  if (isHighCost && record.dailyCount > IP_FREE_LIMIT) {
    return { blocked: true, reason: `高成本模型每日免费额度已用完（${IP_FREE_LIMIT}次），请注册并充值` };
  }
  
  return { blocked: false };
}

// 每小时自动清理IP记录
setInterval(() => {
  const now = Date.now();
  for (const [key, val] of ipRateMap) {
    if (now > val.dailyReset) ipRateMap.delete(key);
  }
}, 3600000);

// ============================================================
// 统一聊天接口（需 API Key 认证）
// ============================================================
// 模型积分表（供API Key认证调用使用）
const API_MODEL_COST = {
  dmx_qwen35_2b_free:0, dmx_qwen3_17b_free:0, dmx_spark_lite_free:0,
  sf_qwen3_8b:0, sf_deepseek_v3_free:0, dmx_qwen3_8b_free:0, dmx_qwen_flash_free:0,
  deepseekv3:1, glm4:1, kimi:1, sf_glm47:0, ali_qwen36_flash:1,
  dmx_minimax_m25_free:0, dmx_glm_47_free:0, dmx_glm_47_flash:0, dmx_glm_45_flash:0,
  dmx_glm_4_9b:0, dmx_hunyuan_lite:0, dmx_qwen35_plus_free:0,
  dmx_qwen3_5_plus_free:0, dmx_qwen35_35b_free:0, dmx_qwen25_coder_7b:0,
  dmx_doubao_seed_lite:0, dmx_mimo_v25_free:0, sf_qwen3_32b:0, or_codeqwen:1,
  glm4plus:1, minimax:1, spark4:1, ali_qwen36_plus:1, ali_deepseek_v4_flash:1,
  sf_hunyuan_a13b:1, sf_qwen35_397b:1, sf_qwq_32b:1,
  dmx_minimax_m27_free:0, dmx_glm_5_turbo_free:0, dmx_qwen3_coder_plus_free:0,
  dmx_qwen3_coder_next_free:0, dmx_doubao_seed_code:0, dmx_mimo_v2_pro_free:0,
  dmx_code_free:0, dmx_codex_free:0, dmx_kat_coder_free:0,
  dmx_qwen36_plus_free:0, dmx_code_free_x:0,
  dmx_kimi_k25_free:0, dmx_kimi_k26_free:0, dmx_doubao_seed_pro:0, dmx_qwen3_max_free:0,
  ark_dbs2_mini:0, ark_dbp15l:0, ark_dbs2_lite:0,
  ark_dsv4f:0, ark_dbs1_6:0, ark_dbs1_8:0, ark_dbs_code:0,
  ark_dsv32:0, ark_dsv4p:0, ark_dbs2_pro:0, ark_glm47:0,
  ark_dbp15p:0, ark_dbs_char:0,
  nx_gpt5:8, nx_gpt5mini:3, nx_gpt5chat:5, nx_gpt5nano:2, nx_gpt5all:8,
  nx_gpt51chat:6, nx_gpt51codex:8, nx_gpt51codexmax:10,
  nx_gpt52chat:8, nx_gpt52pro:8, nx_gpt53chat:18, nx_gpt53codex:25,
  nx_gpt54pro:12, nx_gpt54mini:5, nx_gpt54nano:3,
  nx_gpt55pro:15, nx_gpt55:15,
  nx_claude_opus:25, nx_claude_sonnet:15, nx_claude_haiku:8,
  nx_gemini_pro:12, nx_o3mini:10, nx_dalle3:15, nx_flux:8, nx_suno:15, nx_grok3:15,
  meshy_text:288, meshy_image:288,
  qf_ernie4:5, qf_ernie35:2, qf_ernie_speed:0,
  ark_doubao_pro:0, ark_doubao_lite:0,
  bc_baichuan4:2, bc_baichuan3:1,
  qwen3:2, kimi2:2, minimax1:2, doubao:2, doubao15:2, gpt4omini:2, gemini15flash:2,
  ali_qwen37_max:8, ali_deepseek_v4_pro:2, ali_kimi_k26:2,
  sf_deepseek_v32:1, sf_glm5:2,
  deepseekr1:5, gpt4o:5, hunyuan:5, gemini15pro:5, gemini25flash:5,
  grok3:5, ali_glm51:5, 'mistral-large2':5,
  or_llama3_70b:5, or_mistral_large:5, or_perplexity:5, llama4:3,
  gpt4turbo:10, claude35:10, claude3opus:10, claude4:10,
  claude4opus:15, gemini25pro:10,
  or_gpt4o:10, or_claude_sonnet:10, or_gemini25pro:10,
  qiniu_claude37:10, qiniu_claudeopus4:10, qiniu_gpt4o:10, qiniu_o3:10, qiniu_gemini25pro:10,
  dmx_glm_5_free:0, dmx_glm_51_free:0, dmx_glm_5_turbo_free:0,
};

app.post('/api/chat', async (req, res) => {
  const ip = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
  // 支持两种认证方式：1) API Key (Authorization header) 2) 登录Token (x-auth-token header)
  const apiKey = (req.headers.authorization || '').replace('Bearer ', '');
  const authToken = req.headers['x-auth-token'] || '';
  const { model: modelId, messages } = req.body;

  if (!modelId || !messages) {
    return res.status(400).json({ error: '缺少 model 或 messages 参数' });
  }

  let username = null;
  let userCredits = 0;
  const creditCost = API_MODEL_COST[modelId] !== undefined ? API_MODEL_COST[modelId] : 2;

  // 认证方式1：API Key（第三方接入）
  if (apiKey && apiKey.length > 10) {
    const keyResult = db.exec(
      "SELECT a.username, a.active, u.credits FROM api_keys a JOIN users u ON a.username=u.username WHERE a.api_key=?",
      [apiKey]
    );
    if (!keyResult.length || !keyResult[0].values.length) {
      return res.status(401).json({ error: { message: '无效的 API Key', type: 'auth_error' } });
    }
    const ki = keyResult[0].values[0];
    if (!ki[1]) return res.status(403).json({ error: { message: 'API Key 已被禁用', type: 'auth_error' } });
    username = ki[0];
    userCredits = ki[2] || 0;
  }
  // 认证方式2：登录 Token（网站自身前端）
  else if (authToken && authToken.length > 10) {
    try {
      const payload = JSON.parse(Buffer.from(authToken, 'base64').toString());
      if (payload.username && payload.role && payload.ts) {
        username = payload.username;
        const ur = db.exec("SELECT credits FROM users WHERE username=?", [username]);
        if (ur.length && ur[0].values.length) userCredits = ur[0].values[0][0] || 0;
      }
    } catch(e) { /* token parse error */ }
  }

  // 未认证 → 仅允许免费模型
  if (!username) {
    if (creditCost > 0) {
      return res.status(401).json({ 
        error: { message: '调用收费模型需要 API Key 或登录。请在网站注册并创建 API Key。', type: 'auth_error' } 
      });
    }
    if (modelId && !FREE_ALWAYS.includes(modelId)) {
      return res.status(401).json({
        error: { message: '请先登录或注册后使用该模型，免费注册即送30积分！', type: 'auth_error' }
      });
    }
  } else {
    // 登录用户：检查会员状态和每日免费模型使用限制
    const userResult = db.exec("SELECT membership, membership_expires, daily_free_usage, daily_free_date FROM users WHERE username=?", [username]);
    let membershipInfo = { membership: 'free', expires: '', dailyFreeUsage: 0, dailyFreeDate: '' };
    if (userResult.length && userResult[0].values.length) {
      const r = userResult[0].values[0];
      membershipInfo = { membership: r[0], expires: r[1]||'', dailyFreeUsage: r[2]||0, dailyFreeDate: r[3]||'' };
    }
    const today = new Date().toISOString().slice(0, 10);
    // 非始终免费的模型且有成本 → 计入每日免费限额
    if (creditCost === 0 && !FREE_ALWAYS.includes(modelId)) {
      const dailyUsed = membershipInfo.dailyFreeDate === today ? membershipInfo.dailyFreeUsage : 0;
      const tier = getMembership(membershipInfo);
      if (modelId && dailyUsed >= tier.dailyFreeCalls) {
        return res.status(402).json({
          error: { message: `今日免费模型使用次数已达上限（${tier.dailyFreeCalls}次），开通会员可无限使用`, type: 'membership_required' }
        });
      }
      // 记录使用次数
      if (membershipInfo.dailyFreeDate === today) {
        db.run("UPDATE users SET daily_free_usage=daily_free_usage+1 WHERE username=?", [username]);
      } else {
        db.run("UPDATE users SET daily_free_usage=1, daily_free_date=? WHERE username=?", [today, username]);
      }
      saveDB();
    }
  }

  // IP 速率检查
  const rateCheck = checkIpRate(ip, modelId);
  if (rateCheck.blocked) {
    console.log(`[RATE_LIMIT] ${ip} → ${modelId}: ${rateCheck.reason}`);
    return res.status(429).json({ error: { message: rateCheck.reason, type: 'rate_limit' } });
  }

  // 扣积分
  if (username && creditCost > 0) {
    if (userCredits < creditCost) {
      return res.status(402).json({ error: { message: `积分不足（需要${creditCost}分，当前${userCredits}分）`, type: 'insufficient_credits' } });
    }
    db.run("UPDATE users SET credits=credits-? WHERE username=?", [creditCost, username]);
    db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)", [username, -creditCost, 'API: ' + modelId]);
    if (apiKey) {
      db.run("UPDATE api_keys SET used=used+? WHERE api_key=?", [creditCost, apiKey]);
    }
    saveDB();
  }

  let config = MODEL_CONFIG[modelId];

  // 动态模型路由：根据前缀匹配对应的 API 源
  if (!config) {
    const rawModel = req.body.rawModel || modelId; // 优先用前端传来的原始模型 ID
    if (modelId.startsWith('or_')) {
      const apiKey = process.env.OPENROUTER_API_KEY;
      if (apiKey) {
        const m = rawModel.startsWith('or_') ? rawModel.replace(/^or_/, '') : rawModel;
        config = { provider: 'openai', model: m, baseUrl: 'https://openrouter.ai/api/v1' };
      }
    } else if (modelId.startsWith('sf_')) {
      const apiKey = process.env.SILICONFLOW_API_KEY;
      if (apiKey) {
        const m = rawModel.startsWith('sf_') ? rawModel.replace(/^sf_/, '') : rawModel;
        config = { provider: 'openai', model: m, baseUrl: 'https://api.siliconflow.cn/v1' };
      }
    } else if (modelId.startsWith('ali_')) {
      const apiKey = process.env.DASHSCOPE_API_KEY;
      if (apiKey) {
        const m = rawModel.startsWith('ali_') ? rawModel.replace(/^ali_/, '') : rawModel;
        config = { provider: 'openai', model: m, baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' };
      }
    }
  }

  if (!config) {
    // 完全未知的模型 → 返回错误提示
    console.log(`[UNKNOWN] 未找到模型配置: ${modelId}`);
    const question = messages[messages.length - 1]?.content || '';
    return res.status(400).json({
      model: modelId,
      content: `❌ 模型「${modelId}」未配置\n\n该模型不在当前支持的模型列表中。可能原因：\n1. 该模型为图片/语音/视频等非对话模型\n2. 模型 ID 已变更或下架\n3. 需要联系管理员添加配置\n\n支持列表刷新页面后在"模型选择"中查看。`,
      error: true,
    });
  }

  const providerApiKey = getApiKey(config.provider, modelId);

  // 百度千帆需要实时获取 access token
  let actualApiKey = providerApiKey;
  if (providerApiKey === 'qianfan') {
    actualApiKey = await getQianfanToken();
    if (!actualApiKey) {
      return res.status(500).json({ model: modelId, content: '❌ 百度千帆 Token 获取失败，请检查 AK/SK 配置。', error: true });
    }
  }

  if (!actualApiKey) {
    // 未配置密钥 → 返回错误提示
    console.log(`[NO_KEY] ${modelId} 缺少 API Key`);
    return res.status(500).json({
      model: modelId,
      content: `❌ 模型「${modelId}」API Key 未配置\n\n该模型的后端 API 密钥未设置，暂时无法使用。请联系管理员在服务器环境变量中配置对应的 API Key。`,
      error: true,
    });
  }

  try {
    let content;
    const startTime = Date.now();

    if (config.provider === 'openai' || config.provider === 'qianfan' || config.provider === 'nexus') {
      content = await callOpenAICompatible(config, messages, actualApiKey);
    } else if (config.provider === 'gemini') {
      content = await callGemini(config, messages, actualApiKey);
    } else {
      return res.status(400).json({ error: `不支持的 provider: ${config.provider}` });
    }

    const latency = Date.now() - startTime;
    // 查询剩余积分
    let remainingCredits = null;
    if (username) {
      const cr = db.exec("SELECT credits FROM users WHERE username=?", [username]);
      if (cr.length && cr[0].values.length) remainingCredits = cr[0].values[0][0];
    }

    // SSE 流式响应支持（前端设置 stream: true 时使用）
    if (req.body.stream) {
      res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      // 将完整内容模拟为 SSE 流式输出（按句子拆分，改善体验）
      const sentences = content.split(/(?<=[。！？.!?\n])\s*/);
      for (const sentence of sentences) {
        if (sentence.trim()) {
          const payload = JSON.stringify({ choices: [{ delta: { content: sentence } }] });
          res.write(`data: ${payload}\n\n`);
        }
      }
      res.write('data: [DONE]\n\n');
      res.end();
      return;
    }

    res.json({
      model: modelId,
      content,
      simulated: false,
      latency: `${latency}ms`,
      cost: creditCost,
      credits_remaining: remainingCredits,
    });
  } catch (error) {
    console.error(`[${modelId}] 调用失败:`, error.message);
    res.status(502).json({
      model: modelId,
      content: `❌ API 调用失败: ${error.message}\n\n请检查 API Key 是否正确、账户是否有余额。`,
      error: true,
    });
  }
});

// ============================================================
// 健康检查 & 连接状态
// ============================================================
app.get('/api/status', (req, res) => {
  const providers = {};
  for (const [id, config] of Object.entries(MODEL_CONFIG)) {
    const apiKey = getApiKey(config.provider, id);
    const providerName = config.provider === 'openai'
      ? new URL(config.baseUrl || 'https://api.openai.com').hostname
      : config.provider;
    if (!providers[providerName]) {
      providers[providerName] = { configured: !!apiKey, models: [] };
    }
    providers[providerName].models.push(id);
  }
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    providers,
  });
});

// ============================================================
// 模型列表 API
// ============================================================
app.get('/api/models-list', (req, res) => {
  const allModels = Object.entries(MODEL_CONFIG).map(([id, cfg]) => ({
    id,
    name: cfg.model,
    provider: cfg.baseUrl ? new URL(cfg.baseUrl).hostname : cfg.provider,
    context: '128K',
    inputPrice: '?',
    outputPrice: '?',
    tags: [],
  }));
  res.json({ count: allModels.length, models: allModels });
});

// 别名：前端调用 /api/models，后端实际为 /api/models-list
app.get('/api/models', (req, res) => {
  const allModels = Object.entries(MODEL_CONFIG).map(([id, cfg]) => ({
    id,
    name: cfg.model,
    provider: cfg.baseUrl ? new URL(cfg.baseUrl).hostname : cfg.provider,
    context: '128K',
    inputPrice: '?',
    outputPrice: '?',
    tags: [],
  }));
  res.json({ count: allModels.length, models: allModels });
});

app.get('/api/models-count', async (req, res) => {
  let staticCount = Object.keys(MODEL_CONFIG).length;

  // 尝试并行拉取动态模型计数（应用白名单过滤）
  const tryCount = async (url, headers, filterFn) => {
    try {
      const r = await fetch(url, { headers, signal: AbortSignal.timeout(8000) });
      if (!r.ok) return 0;
      const d = await r.json();
      if (!d?.data) return 0;
      return d.data.filter(m => filterFn(m.id)).length;
    } catch(e) { return 0; }
  };

  let dynamicCount = 0;
  try {
    const [bailian, sf, openrouter] = await Promise.all([
      process.env.DASHSCOPE_API_KEY ? tryCount('https://dashscope.aliyuncs.com/compatible-mode/v1/models', { Authorization: `Bearer ${process.env.DASHSCOPE_API_KEY}` }, isBailianChatModel) : Promise.resolve(0),
      process.env.SILICONFLOW_API_KEY ? tryCount('https://api.siliconflow.cn/v1/models', { Authorization: `Bearer ${process.env.SILICONFLOW_API_KEY}` }, isSiliconFlowChatModel) : Promise.resolve(0),
      process.env.OPENROUTER_API_KEY ? tryCount('https://openrouter.ai/api/v1/models', { Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}` }, isOpenRouterChatModel) : Promise.resolve(0),
    ]);
    dynamicCount = bailian + sf + openrouter;
  } catch(e) { dynamicCount = 0; }

  res.json({ count: staticCount + dynamicCount });
});

// ============================================================
// 模型名称美化工具 - 将 API 原始 ID 转换为人类可读名称
// ============================================================
function beautifyModelName(rawId, platform) {
  let name = rawId;
  // 阿里百炼命名规则
  if (platform === 'bailian') {
    // 第一步：剥离第三方组织前缀
    name = name.replace(/^vanchin\//, '')
               .replace(/^ZHIPU\//, '智谱 ')
               .replace(/^kimi\//, '')
               .replace(/^moonshotai\//, '月之暗面 ')
               .replace(/^deepseek-ai\//, '')
               .replace(/^[a-z0-9][a-z0-9_.-]*\//i, '');
    // 第二步：统一格式（下划线转点/横线）
    name = name.replace(/_/g, '-');
    // 第三步：美化模型名
    name = name.replace(/^qwen3\.([0-9]+)-max/i, '通义千问 3.$1 Max')
               .replace(/^qwen3\.([0-9]+)-plus/i, '通义千问 3.$1 Plus')
               .replace(/^qwen3\.([0-9]+)-flash/i, '通义千问 3.$1 Flash')
               .replace(/^qwen3\.([0-9]+)-coder/i, '通义千问 3.$1 Coder')
               .replace(/^qwen3\.([0-9]+)-([a-z].*)/i, 'Qwen 3.$1 $2')
               .replace(/^qwen3-([0-9a-z]+)/i, '通义千问 3 $1')
               .replace(/^qwen2\.5-([0-9a-z]+)/i, '通义千问 2.5 $1')
               .replace(/^qwen2-([0-9a-z]+)/i, '通义千问 2 $1')
               .replace(/^qwen-(image|video|audio)(.*)/i, 'Qwen $1$2')
               .replace(/^deepseek-v([0-9]+)-pro/i, 'DeepSeek V$1 Pro')
               .replace(/^deepseek-v([0-9]+)-flash/i, 'DeepSeek V$1 Flash')
               .replace(/^deepseek-v([0-9.]+)/i, 'DeepSeek V$1')
               .replace(/^deepseek-r([0-9]+)/i, 'DeepSeek R$1')
               .replace(/^deepseek-ocr/i, 'DeepSeek OCR')
               .replace(/^deepseek-chat/i, 'DeepSeek Chat')
               .replace(/^deepseek-coder/i, 'DeepSeek Coder')
               .replace(/^glm-([0-9.]+)/i, '智谱 GLM-$1')
               .replace(/^kimi-k?([0-9.]+)/i, 'Kimi K$1')
               .replace(/^moonshot/i, '月之暗面')
               .replace(/^doubao/i, '豆包')
               .replace(/^minimax/i, 'MiniMax')
               .replace(/^hunyuan/i, '混元')
               .replace(/^ernie/i, '文心一言')
               .replace(/^spark/i, '讯飞星火')
               .replace(/^baichuan/i, '百川')
               .replace(/^step/i, 'Step')
               .replace(/^yi-/i, '零一万物 ')
               .replace(/^gpt/i, 'GPT')
               .replace(/^claude/i, 'Claude')
               .replace(/^gemini/i, 'Gemini')
               .replace(/^llama/i, 'Llama')
               .replace(/^mistral/i, 'Mistral');
  }
  // 硅基流动命名规则
  if (platform === 'siliconflow') {
    // 第一步：剥离组织前缀
    name = name.replace(/^deepseek-ai\//, '')
               .replace(/^Qwen\//, '')
               .replace(/^Pro\//, '')
               .replace(/^tencent\//, '腾讯 ')
               .replace(/^meta-llama\//, '')
               .replace(/^google\//, 'Google ')
               .replace(/^anthropic\//, '')
               .replace(/^openai\//, '')
               .replace(/^mistralai\//, '')
               .replace(/^01-ai\//, '零一万物 ')
               .replace(/^THUDM\//, '智谱 ')
               .replace(/^internlm\//, '书生 ')
               .replace(/^moonshotai\//, '月之暗面 ')
               .replace(/^minimax\//, 'MiniMax ')
               .replace(/^stepfun-ai\//, 'Step ')
               .replace(/^nvidia\//, 'NVIDIA ')
               .replace(/^microsoft\//, '微软 ')
               .replace(/^x-ai\//, 'xAI ')
               .replace(/^bytedance\//, '字节 ')
               .replace(/^alibaba\//, '阿里 ')
               .replace(/^baichuan-inc\//, '百川 ')
               .replace(/^cohere\//, 'Cohere ')
               .replace(/^stabilityai\//, 'Stability ')
               .replace(/^tiiuae\//, '')
               .replace(/^ai21labs\//, '')
               .replace(/^inclusionai\//, '')
               .replace(/^zhipuai\//, '智谱 ')
               .replace(/^infini\//, '')
               .replace(/^lingyiwanwu\//, '零一万物 ')
               .replace(/^pengcheng\//, '鹏城 ')
               .replace(/^shanghai_ai\//, '')
               .replace(/^togethercomputer\//, '')
               // 通用兜底：匹配任何 org/ 前缀
               .replace(/^[a-z0-9][a-z0-9_.-]*\//i, '');
    // 第二步：美化模型名本身
    name = name.replace(/^deepseek[-_ ]?v([0-9]+)/i, 'DeepSeek V$1')
               .replace(/^deepseek[-_ ]?r([0-9]+)/i, 'DeepSeek R$1')
               .replace(/^deepseek[-_]?coder/i, 'DeepSeek Coder')
               .replace(/^deepseek[-_]?chat/i, 'DeepSeek Chat')
               .replace(/^(DeepSeek)\b\s*$/i, 'DeepSeek')
               .replace(/^glm[-_ ]?([0-9]+[a-z]*)/i, 'GLM-$1')
               .replace(/^glm([0-9]+)/i, 'GLM-$1')
               .replace(/^qwen([0-9]+(?:\.[0-9]+)?)[-_ ]?([a-z].*)/i, 'Qwen $1 $2')
               .replace(/^qwen([0-9]+(?:\.[0-9]+)?)/i, 'Qwen $1')
               .replace(/^hunyuan[-_ ]?(.*)/i, '混元 $1')
               .replace(/^gpt[-_ ]?(.*)/i, 'GPT $1')
               .replace(/^claude[-_ ]?(.*)/i, 'Claude $1')
               .replace(/^gemini[-_ ]?(.*)/i, 'Gemini $1')
               .replace(/^llama[-_ ]?(.*)/i, 'Llama $1')
               .replace(/^mistral[-_ ]?(.*)/i, 'Mistral $1')
               .replace(/^doubao[-_ ]?(.*)/i, '豆包 $1')
               .replace(/^ernie[-_ ]?(.*)/i, '文心一言 $1')
               .replace(/^baichuan[-_ ]?(.*)/i, '百川 $1')
               .replace(/^step[-_ ]?(.*)/i, 'Step $1')
               .replace(/^kimi[-_ ]?k([0-9.]+)/i, 'Kimi K$1')
               .replace(/^moonshot[-_ ]?(.*)/i, '月之暗面 $1')
               .replace(/^minimax[-_ ]?(.*)/i, 'MiniMax $1');
  }
  // OpenRouter 命名规则
  if (platform === 'openrouter') {
    const slashIdx = name.indexOf('/');
    if (slashIdx > 0) name = name.substring(slashIdx + 1);
    name = name.replace(/-/g, ' ')
               .replace(/\b\w/g, c => c.toUpperCase());
    // 还原常见缩写
    name = name.replace(/\bGpt\b/i, 'GPT')
               .replace(/\bGlm\b/i, 'GLM')
               .replace(/\bLlm\b/i, 'LLM')
               .replace(/\bR1\b/i, 'R1')
               .replace(/\bV3\b/i, 'V3')
               .replace(/\bV4\b/i, 'V4')
               // 还原中文品牌名
               .replace(/^Qwen\b/i, '通义千问')
               .replace(/^Deepseek\b/i, 'DeepSeek')
               .replace(/^Gemma\b/i, 'Gemma')
               .replace(/^Mistral\b/i, 'Mistral')
               .replace(/^Claude\b/i, 'Claude')
               .replace(/^Llama\b/i, 'Llama')
               .replace(/^Gemini\b/i, 'Gemini');
  }
  // Fallback: 去掉产商前缀（通用）
  if (name.includes('/') && name !== rawId) {
    name = name.split('/').pop();
  }
  return name;
}

// ============================================================
// 动态模型辅助：生成头像颜色和描述
// ============================================================
const AVATAR_COLORS = ['#10a37f','#d97706','#4285f4','#4f46e5','#ff6a00','#6c5ce7','#6366f1','#e11d48','#059669','#8b5cf6','#ea580c','#0891b2','#7c3aed','#0ea5e9','#e63946','#6b21a8'];
function genAvatarColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = ((hash << 5) - hash) + str.charCodeAt(i);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}
function genModelDesc(name, provider) {
  const descMap = { '阿里云':'阿里云大模型，中文优化', '高性能':'高性能开源模型，按量付费', '海外':'海外模型，全球覆盖' };
  return descMap[provider] || provider + '模型';
}

// 动态模型积分等级（基于名称和大小）
function getDynamicCost(modelId) {
  const id = (modelId || '').toLowerCase();
  // 免费模型
  if (id.includes('免费') || id.includes('free') || id.includes('bge-') || id.includes('embed')) return 0;
  if (/[0-9]{1,2}b/i.test(id) && (id.includes('1.7b') || id.includes('2b') || id.includes('3b') || id.includes('4b') || id.includes('7b') || id.includes('8b'))) return 1;
  if (id.includes('flash') || id.includes('lite') || id.includes('turbo')) return 2;
  if (id.includes('plus') || id.includes('qwen3-') || id.includes('coder')) return 2;
  if (id.includes('max') || id.includes('pro') || id.includes('r1')) return 3;
  if (id.includes('opus') || id.includes('sonnet') || id.includes('gpt-4') || id.includes('claude')) return 10;
  if (id.includes('gemini') && id.includes('pro')) return 10;
  // 默认
  return 3;
}


// ============================================================
// 阿里百炼模型动态拉取
// ============================================================
// 百炼平台已知可用的聊天模型前缀（白名单）
const BAILIAN_CHAT_PREFIX = /^(qwen3\.\d|qwen3-\d|deepseek-v\d|glm-[4-9]|glm-1\d)/i;

function isBailianChatModel(modelId) {
  // 先黑名单过滤非聊天类型
  if (/image|wan|flux|stable|sd[-_]|asr|speech|tts|voice|audio|cosyvoice|gummy|paraformer|sambert|embed|bge[-_]|gte[-_]|video|deep[-_]research|rerank|realtime|MiniMax|kimi-L|abab|moonshot|step[-_]/i.test(modelId)) return false;
  // 再白名单验证是否为已知可用的聊天模型
  return BAILIAN_CHAT_PREFIX.test(modelId);
}

app.get('/api/bailian-models', async (req, res) => {
  const apiKey = process.env.DASHSCOPE_API_KEY;
  if (!apiKey) return res.json({ ok: false, models: [] });
  try {
    const r = await fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/models', {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await r.json();
    const models = (data.data || [])
      .filter(m => isBailianChatModel(m.id))  // 白名单+黑名单双重过滤
      .map(m => {
        const name = beautifyModelName(m.id, 'bailian');
        return {
          id: 'ali_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
          name,
          rawModel: m.id,
          avatar: genAvatarColor(name),
          desc: genModelDesc(name, '阿里云'),
          provider: '阿里云',
          context: '128K',
          inputPrice: (m.id || '').includes('免费') ? '免费' : '按量',
          outputPrice: (m.id || '').includes('免费') ? '免费' : '按量',
          tags: [],
          platform: 'bailian',
          free: (m.id || '').includes('免费'),
          cost: getDynamicCost(m.id),
        };
      });
    res.json({ ok: true, count: models.length, models, filtered: (data.data||[]).length - models.length });
  } catch(e) {
    res.json({ ok: false, models: [] });
  }
});

// ============================================================
// 硅基流动模型动态拉取
// ============================================================
// 硅基流动已知可用的聊天模型前缀
const SILICONFLOW_CHAT_PREFIX = /^(Qwen\/Qwen3|Qwen\/QwQ|Qwen\/Qwen2\.5|deepseek-ai\/DeepSeek-V3|deepseek-ai\/DeepSeek-R1|Pro\/zai-org\/GLM|tencent\/Hunyuan|meta-llama\/Llama-4|meta-llama\/Llama-3\.[1-9]|mistralai\/Mistral|THUDM\/glm|01-ai\/Yi|internlm\/)/i;
const SF_NON_CHAT = /image|flux|stable|sd[-_]|video|cogvideo|embed|bge|asr|speech|tts|voice|audio/i;

function isSiliconFlowChatModel(modelId) {
  if (SF_NON_CHAT.test(modelId)) return false;
  return SILICONFLOW_CHAT_PREFIX.test(modelId);
}

app.get('/api/siliconflow-models', async (req, res) => {
  const apiKey = process.env.SILICONFLOW_API_KEY;
  if (!apiKey) return res.json({ ok: false, models: [] });
  try {
    const r = await fetch('https://api.siliconflow.cn/v1/models', {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await r.json();
    const models = (data.data || [])
      .filter(m => isSiliconFlowChatModel(m.id))  // 白名单过滤
      .map(m => {
        const name = beautifyModelName(m.id, 'siliconflow');
        return {
          id: 'sf_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
          name,
          rawModel: m.id,
          avatar: genAvatarColor(name),
          desc: genModelDesc(name, '高性能'),
          provider: '高性能',
          context: '64K',
          inputPrice: (m.id || '').includes('free') || (m.id || '').includes('免费') ? '免费' : '按量',
          outputPrice: (m.id || '').includes('free') || (m.id || '').includes('免费') ? '免费' : '按量',
          tags: [],
          platform: 'siliconflow',
          free: (m.id || '').includes('free') || (m.id || '').includes('免费'),
          cost: getDynamicCost(m.id),
        };
      });
    res.json({ ok: true, count: models.length, models, filtered: (data.data||[]).length - models.length });
  } catch(e) {
    res.json({ ok: false, models: [] });
  }
});

// ============================================================
// OpenRouter 模型动态拉取
// ============================================================
// OpenRouter 已知可用的主流聊天模型前缀
const OPENROUTER_CHAT_PREFIX = /^(openai\/gpt-4|openai\/gpt-5|openai\/o[1-9]|anthropic\/claude-|google\/gemini-2|google\/gemini-1\.5|meta-llama\/llama-4|meta-llama\/llama-3\.[1-9]|mistralai\/mistral-large|mistralai\/mistral-small|qwen\/qwen-2\.5|qwen\/qwen3|deepseek\/deepseek-v|deepseek\/deepseek-r|perplexity\/|cohere\/command-r|amazon\/nova)/i;
const OR_NON_CHAT = /image|video|audio|tts|speech|embed|moderation/i;

function isOpenRouterChatModel(modelId) {
  if (OR_NON_CHAT.test(modelId)) return false;
  return OPENROUTER_CHAT_PREFIX.test(modelId);
}

app.get('/api/openrouter-models', async (req, res) => {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) return res.json({ ok: false, models: [] });
  try {
    const r = await fetch('https://openrouter.ai/api/v1/models', {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await r.json();
    const models = (data.data || [])
      .filter(m => isOpenRouterChatModel(m.id))  // 白名单过滤
      .map(m => {
        const name = beautifyModelName(m.id, 'openrouter');
        return {
          id: 'or_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
          name,
          rawModel: m.id,
          avatar: genAvatarColor(name),
          desc: genModelDesc(name, '海外'),
          provider: '海外',
          context: (m.context_length || '128K') + '',
          inputPrice: m.pricing ? (m.pricing.prompt || '?') : '?',
          outputPrice: m.pricing ? (m.pricing.completion || '?') : '?',
          tags: [],
          platform: 'openrouter',
          free: false,
          cost: getDynamicCost(m.id),
        };
      });
    res.json({ ok: true, count: models.length, models, filtered: (data.data||[]).length - models.length });
  } catch(e) {
    res.json({ ok: false, models: [] });
  }
});

// ============================================================
// ============================================================
// Meshy 3D 模型生成 API
// ============================================================
app.post('/api/meshy/txt2d', async (req, res) => {
  try {
    const apiKey = process.env.MESHY_API_KEY;
    if (!apiKey) return res.json({ ok: false, error: 'Meshy API Key 未配置' });

    const { prompt, style = 'realistic' } = req.body;
    if (!prompt) return res.json({ ok: false, error: '请输入3D模型描述' });

    const r = await fetch('https://api.meshy.ai/openapi/v2/text-to-3d', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + apiKey,
      },
      body: JSON.stringify({
        mode: 'preview',
        prompt,
        style_prompt: style,
        enable_pbr: true,
      }),
    });
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

app.get('/api/meshy/result/:taskId', async (req, res) => {
  try {
    const apiKey = process.env.MESHY_API_KEY;
    if (!apiKey) return res.json({ ok: false });

    const r = await fetch('https://api.meshy.ai/openapi/v2/text-to-3d/' + req.params.taskId, {
      headers: { 'Authorization': 'Bearer ' + apiKey },
    });
    res.json(await r.json());
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

// ============================================================
// Agnes AI 视频生成代理（异步：提交 → 轮询）
// ============================================================
app.post('/api/agnes-video', async (req, res) => {
  try {
    const apiKey = process.env.AGNES_API_KEY;
    if (!apiKey) return res.json({ ok: false, error: 'Agnes API Key 未配置' });

    const { prompt, width, height, num_frames, frame_rate, negative_prompt, seed, image, mode } = req.body;
    if (!prompt) return res.json({ ok: false, error: '缺少视频描述' });

    const body = {
      model: 'agnes-video-v2.0',
      prompt: prompt,
      width: width || 1152,
      height: height || 768,
      num_frames: num_frames || 121,
      frame_rate: frame_rate || 24,
    };
    if (negative_prompt) body.negative_prompt = negative_prompt;
    if (seed != null) body.seed = seed;
    if (image) body.image = image;
    if (mode) body.mode = mode;

    const r = await fetch('https://apihub.agnes-ai.com/v1/videos', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    res.json({ ok: true, ...data });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

app.get('/api/agnes-video/:taskId', async (req, res) => {
  try {
    const apiKey = process.env.AGNES_API_KEY;
    if (!apiKey) return res.json({ ok: false, error: 'Agnes API Key 未配置' });

    const r = await fetch('https://apihub.agnes-ai.com/v1/videos/' + req.params.taskId, {
      headers: { 'Authorization': 'Bearer ' + apiKey },
    });
    const data = await r.json();
    res.json({ ok: true, ...data });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

// ============================================================
// Suno 音乐 API 代理
// ============================================================
const SUNO_BASE = process.env.SUNO_API_BASE || 'https://open.suno.cn/api/v1';
const SUNO_KEY = process.env.SUNO_API_KEY || '';

// 提交音乐生成
app.post('/api/music/generate', async (req, res) => {
  const { prompt, title, instrumental, model } = req.body;
  if (!SUNO_KEY) return res.json({ ok: false, error: 'Suno API Key 未配置' });
  try {
    const body = {
      gpt_description_prompt: prompt,
      make_instrumental: !!instrumental,
      mv: model || 'chirp-crow',
      title: title || '未命名歌曲'
    };
    const r = await fetch(`${SUNO_BASE}/music/generate`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${SUNO_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await r.json();
    res.json(data);
  } catch(e) {
    res.status(500).json({ ok: false, error: 'Suno API 调用失败: ' + e.message });
  }
});

// 查询音乐生成结果
app.get('/api/music/task', async (req, res) => {
  const { id } = req.query;
  if (!id) return res.json({ ok: false, error: '缺少 task_id' });
  try {
    const r = await fetch(`${SUNO_BASE}/music/task?id=${id}`, {
      headers: { 'Authorization': `Bearer ${SUNO_KEY}` }
    });
    const data = await r.json();
    res.json(data);
  } catch(e) {
    res.status(500).json({ ok: false, error: '查询失败: ' + e.message });
  }
});

// ============================================================
// 可灵 Kling 视频生成 API
// ============================================================
const KLING_AK = process.env.KLING_AK || '';
const KLING_SK = process.env.KLING_SK || '';
const KLING_BASE = 'https://api.klingai.com';

function generateKlingToken() {
  const now = Math.floor(Date.now() / 1000);
  return jwt.sign(
    { iss: KLING_AK, exp: now + 1800, nbf: now - 5 },
    KLING_SK,
    { algorithm: 'HS256', header: { alg: 'HS256', typ: 'JWT' } }
  );
}

// 文生视频
app.post('/api/kling/text2video', async (req, res) => {
  try {
    const { prompt, model = 'kling-v1.6', duration = 5, mode = 'pro' } = req.body;
    if (!prompt) return res.status(400).json({ error: '请输入提示词' });
    const token = generateKlingToken();
    const r = await fetch(`${KLING_BASE}/v1/videos/text2video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ model_name: model, prompt, duration, mode, image_tailor: 'none' })
    });
    res.json(await r.json());
  } catch(e) {
    res.status(500).json({ error: '视频生成失败: ' + e.message });
  }
});

// 图生视频
app.post('/api/kling/image2video', async (req, res) => {
  try {
    const { image, prompt, model = 'kling-v1.6', duration = 5 } = req.body;
    if (!image) return res.status(400).json({ error: '请上传图片' });
    const token = generateKlingToken();
    const r = await fetch(`${KLING_BASE}/v1/videos/image2video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ model_name: model, image, prompt: prompt || '', duration, mode: 'pro' })
    });
    res.json(await r.json());
  } catch(e) {
    res.status(500).json({ error: '图生视频失败: ' + e.message });
  }
});

// 查询任务状态
app.get('/api/kling/task', async (req, res) => {
  try {
    const { id } = req.query;
    if (!id) return res.status(400).json({ error: '缺少任务ID' });
    const token = generateKlingToken();
    const r = await fetch(`${KLING_BASE}/v1/videos/${id}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    res.json(await r.json());
  } catch(e) {
    res.status(500).json({ error: '查询任务失败: ' + e.message });
  }
});

// ============================================================
// SQLite 数据库
// ============================================================
let db = null;
const DB_FILE = path.join(__dirname, 'data.db');
const SQL = require('sql.js');
async function initDB() {
  const initSql = fs.existsSync(DB_FILE) ? fs.readFileSync(DB_FILE) : null;
  const sql = await SQL({
    locateFile: file => path.join(__dirname, 'node_modules', 'sql.js', 'dist', file)
  });
  db = new sql.Database(initSql);
  db.run(`CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    credits INTEGER DEFAULT 30,
    ref_code TEXT,
    referrer TEXT,
    role TEXT DEFAULT 'user',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  // 数据库迁移：添加新字段（兼容已有数据库）
  try { db.run(`ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN register_ip TEXT DEFAULT ''`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN device_fp TEXT DEFAULT ''`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN security_q TEXT DEFAULT ''`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN security_a TEXT DEFAULT ''`); } catch(e) {}
  // === 会员体系 ===
  try { db.run(`ALTER TABLE users ADD COLUMN membership TEXT DEFAULT 'free'`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN membership_expires TEXT DEFAULT ''`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN daily_free_usage INTEGER DEFAULT 0`); } catch(e) {}
  try { db.run(`ALTER TABLE users ADD COLUMN daily_free_date TEXT DEFAULT ''`); } catch(e) {}
  // === 访客设备指纹表（反作弊积分持久化） ===
  db.run(`CREATE TABLE IF NOT EXISTS guest_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    ip TEXT DEFAULT '',
    credits_used INTEGER DEFAULT 0,
    daily_credits INTEGER DEFAULT 0,
    last_reset_date TEXT DEFAULT '',
    first_seen TEXT DEFAULT (datetime('now', 'localtime')),
    last_seen TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  try { db.run(`CREATE INDEX IF NOT EXISTS idx_guest_fp ON guest_fingerprints(fingerprint)`); } catch(e) {}
  // === API Key 表 ===
  db.run(`CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    key_name TEXT DEFAULT '',
    api_key TEXT UNIQUE NOT NULL,
    quota INTEGER DEFAULT 0,
    used INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  db.run(`CREATE TABLE IF NOT EXISTS credit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT,
    admin TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  db.run(`CREATE TABLE IF NOT EXISTS key_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    prefix TEXT NOT NULL,
    models TEXT,
    manage_url TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  // === 知识库表 (RAG) ===
  db.run(`CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    tags TEXT DEFAULT '',
    source TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  // 为知识库建全文搜索索引
  try { db.run(`CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_base(category)`); } catch(e) {}
  try { db.run(`CREATE INDEX IF NOT EXISTS idx_knowledge_updated ON knowledge_base(updated_at)`); } catch(e) {}
  // === AI 小说相关表 ===
  db.run(`CREATE TABLE IF NOT EXISTS novels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL, title TEXT DEFAULT '未命名作品',
    type TEXT DEFAULT '', outline TEXT DEFAULT '', core TEXT DEFAULT '',
    total_words INTEGER DEFAULT 0, chapter_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  try { db.run('CREATE INDEX IF NOT EXISTS idx_novels_username ON novels(username)'); } catch(e) {}
  db.run(`CREATE TABLE IF NOT EXISTS novel_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL, novel_id INTEGER DEFAULT 0,
    name TEXT NOT NULL, avatar TEXT DEFAULT '',
    gender TEXT DEFAULT '', age TEXT DEFAULT '',
    appearance TEXT DEFAULT '', personality TEXT DEFAULT '',
    background TEXT DEFAULT '', goal TEXT DEFAULT '',
    arc TEXT DEFAULT '', notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  try { db.run('CREATE INDEX IF NOT EXISTS idx_characters_novel ON novel_characters(novel_id)'); } catch(e) {}
  db.run(`CREATE TABLE IF NOT EXISTS novel_worlds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL, novel_id INTEGER DEFAULT 0,
    category TEXT DEFAULT 'general', key TEXT NOT NULL,
    value TEXT DEFAULT '', description TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  try { db.run('CREATE INDEX IF NOT EXISTS idx_worlds_novel ON novel_worlds(novel_id)'); } catch(e) {}
  db.run(`CREATE TABLE IF NOT EXISTS novel_chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL, novel_id INTEGER DEFAULT 0,
    chapter_index INTEGER DEFAULT 0, title TEXT DEFAULT '',
    content TEXT DEFAULT '', outline TEXT DEFAULT '',
    word_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  try { db.run('CREATE INDEX IF NOT EXISTS idx_chapters_novel ON novel_chapters(novel_id)'); } catch(e) {}
  db.run(`CREATE TABLE IF NOT EXISTS novel_chapter_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL, username TEXT NOT NULL,
    version INTEGER DEFAULT 1, content TEXT NOT NULL,
    summary TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
  )`);
  try { db.run('CREATE INDEX IF NOT EXISTS idx_versions_chapter ON novel_chapter_versions(chapter_id)'); } catch(e) {}

  // 确保有 admin 用户
  const adminExists = db.exec("SELECT id FROM users WHERE username='admin'");
  if (!adminExists.length || !adminExists[0].values.length) {
    db.run("INSERT INTO users (username, email, password, credits, role) VALUES (?, ?, ?, ?, ?)",
      ['admin', 'admin@j3trisheng.com', hashPasswordSync('admin888'), 9999, 'admin']);
  }
  // 初始化知识库种子数据（仅当表为空时）
  const kbCount = db.exec("SELECT COUNT(*) FROM knowledge_base");
  const kbEmpty = !kbCount.length || !kbCount[0].values.length || kbCount[0].values[0][0] === 0;
  if (kbEmpty) {
    const seeds = [
      // === 平台基础 ===
      ['平台介绍', 'Nexus Hub 是一个智能创作平台，聚合全球顶尖大语言模型，无需注册多个账户即可一站体验。支持多模型对比、智能路由、RAG 知识增强、积分通用等功能。涵盖聊天、写作、绘图、视频、3D、音乐等全方位 AI 能力。', 'platform', '平台,介绍,聚合,AI'],
      ['会员权益', '注册即送 30 积分。根据不同模型消耗 1-10 积分/次。积分通用，一个账户畅享所有 AI 服务。会员订阅更划算，最低 ¥49/月。', 'pricing', '积分,充值,会员,价格,订阅'],
      ['隐私保护', '用户对话不长期存储，对话仅用于实时生成回复。知识库内容加密存储。我们承诺不将用户数据用于 AI 模型训练或任何商业用途。', 'platform', '隐私,安全,数据'],

      // === 聊天 ===
      ['多模型聊天', 'AI 聊天支持同时选择多个模型对话。输入一个问题，可同时获得多个模型的回答并直观对比。支持 RAG 知识增强——输入框上方勾选开关后，每次提问会自动检索平台知识库，注入相关背景信息，让回答更精准。', 'chat', '聊天,多模型,对比,RAG'],
      ['RAG 知识增强', 'RAG（检索增强生成）是 Nexus Hub 的核心特色功能。启用后，每次对话前系统会从知识库中检索相关内容，注入到对话上下文中。这意味着 AI 回答会基于平台的最新信息，而非仅依赖训练数据。用户可通过「知识库」按钮管理自己的知识条目。', 'chat', 'RAG,知识增强,检索,对话'],

      // === 小说 ===
      ['AI 小说创作', '小说创作提供完整六步流程：确定方向→搭建框架→锁定框架→编写大纲→确认大纲→逐章写作。系统自动注入大纲约束、人物档案和前文摘要，确保长篇小说前后连贯。支持快速创作、分步指导和灵感火花三种模式。', 'novel', '小说,创作,大纲,写作,长文'],
      ['小说写作技巧', '创作建议：1) 先确定类型和风格 2) 利用人物模块建立角色库 3) 大纲越详细成稿质量越高 4) 每章写完后检查前文回顾 5) 使用「去AI痕迹」功能让文风更自然。平台支持百万字长篇创作，提供分章节管理和导出功能。', 'novel', '写作,技巧,建议,长文'],

      // === 漫剧 ===
      ['AI 漫剧工厂', '漫剧功能支持将小说自动转为漫画脚本。包含分镜脚本生成、角色设计参考、场景描述等功能。适合将已有小说作品可视化呈现，也支持独立创作漫画故事。', 'comic', '漫剧,漫画,分镜,脚本'],

      // === 智能体 ===
      ['AI 智能体', '智能体工坊提供 10+ 预置专家智能体：编程导师、文案写手、翻译专家、数据分析师、法律顾问、健康助手等。每个智能体拥有专属系统提示和领域知识，比通用聊天更专业。支持自定义创建专属智能体。', 'agent', '智能体,专家,自定义,领域'],

      // === 办公 ===
      ['智能办公工具', '办公模块集成多种职场工具：工作总结生成、PPT 大纲、会议纪要整理、邮件撰写、简历优化、公文写作等。选择对应模板，输入关键信息即可快速生成专业文档。', 'office', '办公,总结,PPT,邮件,简历'],

      // === 品牌 ===
      ['品牌设计', '品牌模块提供企业命名、Slogan 生成、品牌故事撰写、Logo 设计理念、品牌配色方案等功能。帮助创业者从零搭建品牌体系。输入行业和目标人群即可获得定制方案。', 'brand', '品牌,命名,Slogan,Logo,创业'],

      // === 营销 ===
      ['智能营销', '营销工具覆盖主流内容平台：小红书文案、公众号文章、短视频脚本、朋友圈文案、产品详情页、SEO 标题优化等。根据平台特性和目标受众自动调整文案风格和长度。', 'marketing', '营销,小红书,公众号,文案,短视频'],

      // === 创作工场 ===
      ['AI 创作工场', '创作工场提供文字转图像、文字转视频功能。输入画面描述即可生成高质量图像，支持多种风格（写实、动漫、油画、水墨等）。视频生成支持 cinematic 电影级画面，内置 20+ 示例模板可直接使用。', 'studio', '创作,绘图,视频,AI'],

      // === 提示词库 ===
      ['提示词库', '提示词库内置 50+ 写作辅助工具：小说开篇生成、人物对话润色、场景描写、情感渲染、冲突设计等。每个工具都经过专业调优，帮助创作者突破瓶颈。支持自定义提示词模板。', 'prompt', '提示词,写作,模板,润色'],

      // === 3D 生成 ===
      ['3D 模型生成', '支持文字转 3D 模型和图片转 3D 模型。输入描述或上传参考图即可生成可用于游戏、影视、3D 打印的低面数模型。生成后可在线预览并下载通用格式文件。', '3d', '3D,模型,建模,游戏'],

      // === AI 音乐 ===
      ['AI 音乐创作', 'AI 音乐模块支持输入歌词、选择音乐风格（流行、古风、电子、爵士等）一键生成原创歌曲。提供多种声线和编曲风格选项，适合内容创作者、短视频制作者、独立音乐人使用。', 'music', '音乐,歌曲,作曲,编曲'],

      // === 工具箱 ===
      ['实用工具箱', '工具箱集成常用实用功能：图片去水印、图片拼接、图片压缩、在线取色器、图片隐写术、Base64 编解码、JSON 格式化、二维码生成等。全部免费使用，无需下载安装。', 'tools', '工具箱,图片处理,编码,实用'],

      // === 模型与对比 ===
      ['模型对比', '支持同时选择 2-4 个模型对比同一问题的回答。直观展示各模型的推理速度、输出长度和内容差异。适合评估不同模型的能力边界，为特定任务选择最优模型。', 'platform', '对比,模型,评估'],
      ['模型选择建议', '不同场景推荐：长篇创作选推理能力强的模型，快速问答选响应快的轻量模型，多模态任务选支持图像理解的模型，代码编程选专门优化过的编程模型。模型目录页面可按类别和标签筛选。', 'platform', '模型,选择,推荐,场景'],

      // === 注册与账户 ===
      ['注册方式', '支持手机号注册，每个手机号限一个账号。新用户注册即送 30 积分。支持邀请码注册，邀请人与被邀请人各得 30 积分奖励。', 'account', '注册,手机号,邀请码,积分'],
      ['签到奖励', '每日签到获得 5 积分奖励，连续签到天数越多奖励越丰厚（第7天+5）。签到积分每日刷新，可在顶部导航栏点击签到按钮查看当日奖励。', 'account', '签到,奖励,积分'],

      // === 充值 ===
      ['充值套餐', '提供多种积分套餐：体验包 180 积分 ¥9.9、标准包 900 积分 ¥39、进阶包 1800 积分 ¥69。月卡 ¥29/月送 900 积分，季卡 ¥119/季送 4500 积分，年卡 ¥399/年送 18250 积分。积分永久有效。', 'pricing', '充值,套餐,价格,积分'],

      // === 知识库 ===
      ['知识库管理', '知识库是 RAG 系统的数据基础。用户可以添加、编辑、删除知识条目，支持按分类和标签管理。知识条目会被自动索引，在启用 RAG 增强的对话中自动检索匹配。建议将产品文档、FAQ、创作素材等存入知识库。', 'knowledge', '知识库,管理,RAG,数据'],

      // === 其他 ===
      ['反馈与支持', '如有功能建议、Bug 反馈或使用疑问，可通过反馈页面提交。我们会根据用户反馈持续优化平台功能。也欢迎通过联系页面提供商业合作建议。', 'support', '反馈,支持,建议,联系'],
      ['模型积分说明', 'Nexus Hub 模型按能力分为八个等级：免费（轻量模型不限次）、1积分（入门如DS-V3）、2积分（进阶如Qwen3.6-Plus）、3积分（高级）、5积分（旗舰如GPT-4o/DS-R1）、10积分（尊享如Claude/Gemini Pro）、20-80积分（海外旗舰如GPT-5/Claude Opus）、288积分（3D模型生成）。免费模型不限次数，付费模型按次消耗积分。积分永不过期。', 'pricing', '积分,模型,价格,等级'],
      ['新用户指南', '首次使用建议：1) 注册领取30积分 2) 在Chat页面勾选RAG知识增强获得更精准回答 3) 从1积分模型开始体验 4) 尝试多模型对比功能感受不同AI的回答差异 5) 将常用提示词存入知识库。月度会员¥49最划算，适合深度使用。', 'platform', '新用户,指南,入门,教程'],
    ];
    const stmt = db.prepare("INSERT INTO knowledge_base (title, content, category, tags) VALUES (?,?,?,?)");
    for (const s of seeds) { stmt.run(s); }
    stmt.free();
    saveDB();
    console.log('知识库种子数据已初始化 (' + seeds.length + ' 条)');
  }

  saveDB();
  console.log('数据库已就绪');
}

function btoaPwd(pwd) {
  return Buffer.from(pwd).toString('base64');
}

// 判断是否为 bcrypt 哈希格式
function isBcryptHash(hash) {
  return typeof hash === 'string' && hash.startsWith('$2b$');
}

// 使用 bcrypt 哈希密码（同步，用于最小化代码改动）
function hashPasswordSync(pwd) {
  return bcrypt.hashSync(pwd, SALT_ROUNDS);
}

// 验证密码（兼容 bcrypt 和旧版 Base64，同步）
function verifyPasswordSync(pwd, storedHash) {
  if (isBcryptHash(storedHash)) {
    return bcrypt.compareSync(pwd, storedHash);
  }
  // 兼容旧版 Base64 编码的密码
  return storedHash === btoaPwd(pwd);
}

// 升级旧版 Base64 密码为 bcrypt（在验证成功后调用）
function upgradePasswordToBcrypt(username, plainPwd) {
  const newHash = hashPasswordSync(plainPwd);
  db.run("UPDATE users SET password=? WHERE username=?", [newHash, username]);
  saveDB();
}

function saveDB() {
  try {
    const data = db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(DB_FILE, buffer);
  } catch(e) { console.error('保存数据库失败:', e.message); }
}

// ============================================================
// 认证 API
// ============================================================
app.post('/api/auth/register', authLimiter, (req, res) => {
  const { username, email, password, refCode, deviceFp } = req.body;
  if (!username || !password) {
    return res.json({ ok: false, error: '请填写用户名和密码' });
  }
  const phone = (req.body.phone || '').trim();
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
    return res.json({ ok: false, error: '请填写正确的手机号' });
  }
  if (!/^[a-zA-Z0-9]{2,20}$/.test(username)) {
    return res.json({ ok: false, error: '用户名格式不正确（2-20位字母或数字）' });
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.json({ ok: false, error: '邮箱格式不正确' });
  }
  if (password.length < 6) {
    return res.json({ ok: false, error: '密码至少6位' });
  }
  const securityQ = (req.body.securityQuestion || '').trim();
  const securityA = (req.body.securityA || '').trim();
  if (!securityQ || !securityA) {
    return res.json({ ok: false, error: '请设置密保问题和答案' });
  }
  // === 防多账号：同一IP永久最多注册2个账号 ===
  const clientIP = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
  const ipCount = db.exec("SELECT COUNT(*) FROM users WHERE register_ip=?", [clientIP]);
  const currentCount = (ipCount.length && ipCount[0].values.length) ? ipCount[0].values[0][0] : 0;
  if (currentCount >= 2) {
    return res.json({ ok: false, error: '本网络已注册过 2 个账号，已达到上限' });
  }
  // === 防多账号：同一设备指纹最多注册 1 个账号 ===
  if (deviceFp && deviceFp.length >= 8) {
    const fpCount = db.exec("SELECT COUNT(*) FROM users WHERE device_fp=?", [deviceFp]);
    const currentFpCount = (fpCount.length && fpCount[0].values.length) ? fpCount[0].values[0][0] : 0;
    if (currentFpCount >= 1) {
      return res.json({ ok: false, error: '该设备已注册过账号，每个设备限注册一个账号' });
    }
  }
  try {
    const existing = db.exec("SELECT id FROM users WHERE username=? " + (email ? "OR email=?" : "") + " OR phone=?", 
      email ? [username, email, phone] : [username, phone]);
    if (existing.length && existing[0].values.length) {
      return res.json({ ok: false, error: '用户名、邮箱或手机号已被注册' });
    }
    const refCodeGen = 'J3' + username.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6) + Math.random().toString(36).slice(2, 5).toUpperCase();
    const userEmail = email || ('noemail_' + username + '@nexus-hub.local');
    let bonus = 30; // 注册赠送
    let referrer = null;
    if (refCode) {
      const refUser = db.exec("SELECT username FROM users WHERE ref_code=? OR username=?", [refCode, refCode]);
      if (refUser.length && refUser[0].values.length) {
        bonus += 30;
        referrer = refUser[0].values[0][0];
        db.run("UPDATE users SET credits=credits+30 WHERE username=?", [referrer]);
        db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?, ?, ?)", [referrer, 30, '推荐奖励']);
      }
    }
    db.run("INSERT INTO users (username, email, password, credits, ref_code, referrer, register_ip, phone, device_fp, security_q, security_a) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
      [username, userEmail, hashPasswordSync(password), bonus, refCodeGen, referrer, clientIP, phone||'', deviceFp||'', securityQ, hashPasswordSync(securityA)]);
    db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)", [username, bonus, '注册赠送']);
    // 自动生成 API Key
    const apiKey = 'nexus-' + username.substring(0,4).toLowerCase() + '-' + crypto.randomBytes(6).toString('hex');
    db.run("INSERT INTO api_keys (username, key_name, api_key, quota) VALUES (?,?,?,?)", [username, '默认Key', apiKey, 0]);
    saveDB();
    const token = signToken({ username, role: 'user', ts: Date.now() });
    res.json({ ok: true, token, apiKey, user: { username, email, credits: bonus, refCode: refCodeGen }, bonus, referrerBonus: refCode ? 30 : 0 });
  } catch(e) {
    res.json({ ok: false, error: '注册失败: ' + e.message });
  }
});

app.post('/api/auth/login', authLimiter, (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.json({ ok: false, error: '请输入用户名和密码' });
  }
  try {
    const result = db.exec("SELECT username, email, password, credits, role, ref_code FROM users WHERE username=? OR email=? OR phone=?",
      [username, username, username]);
    if (!result.length || !result[0].values.length) {
      return res.json({ ok: false, error: '用户不存在' });
    }
    const user = result[0].values[0];
    if (!verifyPasswordSync(password, user[2])) {
      return res.json({ ok: false, error: '密码错误' });
    }
    // 如果是旧版 Base64 密码，自动升级为 bcrypt
    if (!isBcryptHash(user[2])) {
      upgradePasswordToBcrypt(user[0], password);
    }
    const token = signToken({ username: user[0], role: user[4], ts: Date.now() });
    const apiKeyResult = db.exec("SELECT api_key FROM api_keys WHERE username=? ORDER BY id LIMIT 1", [user[0]]);
    const apiKey = apiKeyResult.length && apiKeyResult[0].values.length ? apiKeyResult[0].values[0][0] : null;
    res.json({ ok: true, token, apiKey, user: { username: user[0], email: user[1], credits: user[3], role: user[4], refCode: user[5] } });
  } catch(e) {
    res.json({ ok: false, error: '登录失败: ' + e.message });
  }
});

// 用户消费积分（登录后调用，同步到数据库）
app.post('/api/user/spend', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  const { amount } = req.body;
  if (!amount || amount <= 0) {
    return res.json({ ok: false, error: '金额无效' });
  }
  try {
    const payload = verifyToken(token);
    const username = payload.username;
    const user = db.exec("SELECT credits FROM users WHERE username=?", [username]);
    if (!user.length || !user[0].values.length) {
      return res.json({ ok: false, error: '用户不存在' });
    }
    const current = user[0].values[0][0];
    if (current < amount) {
      return res.json({ ok: false, error: '积分不足' });
    }
    db.run("UPDATE users SET credits=credits-? WHERE username=?", [amount, username]);
    db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)", [username, -amount, '消费']);
    saveDB();
    const newCredits = db.exec("SELECT credits FROM users WHERE username=?", [username]);
    res.json({ ok: true, credits: newCredits[0].values[0][0] });
  } catch(e) {
    res.json({ ok: false, error: e.message });
  }
});

// 获取用户积分
app.get('/api/user/credits', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  try {
    const payload = verifyToken(token);
    const user = db.exec("SELECT credits FROM users WHERE username=?", [payload.username]);
    if (!user.length || !user[0].values.length) {
      return res.json({ ok: false, error: '用户不存在' });
    }
    res.json({ ok: true, credits: user[0].values[0][0] });
  } catch(e) {
    res.json({ ok: false, error: e.message });
  }
});

// 退款（API 调用失败时）

// 退款（API 调用失败时）
app.post('/api/user/refund', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  const { amount } = req.body;
  if (!amount || amount <= 0) return res.json({ ok: false, error: '金额无效' });
  try {
    const payload = verifyToken(token);
    const username = payload.username;
    db.run("UPDATE users SET credits=credits+? WHERE username=?", [amount, username]);
    db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)", [username, amount, '退款-API失败']);
    saveDB();
    const newCredits = db.exec("SELECT credits FROM users WHERE username=?", [username]);
    res.json({ ok: true, credits: newCredits[0].values[0][0] });
  } catch(e) {
    res.json({ ok: false, error: e.message });
  }
});

// ============================================================
// 管理员 API（手动充值、查看用户）
// ============================================================
function requireAdmin(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ ok: false, error: '未登录' });
  }
  try {
    const payload = JSON.parse(Buffer.from(auth.slice(7), 'base64').toString());
    if (payload.role !== 'admin') {
      return res.status(403).json({ ok: false, error: '无管理员权限' });
    }
    req.adminUser = payload.username;
    next();
  } catch(e) {
    return res.status(401).json({ ok: false, error: 'Token无效' });
  }
}

// 管理员登录
app.post('/api/admin/login', (req, res) => {
  const { password } = req.body;
  try {
    const result = db.exec("SELECT username, password FROM users WHERE role='admin' AND username='admin'");
    if (!result.length || !result[0].values.length) {
      return res.json({ ok: false, error: '管理员账号不存在' });
    }
    const admin = result[0].values[0];
    if (!verifyPasswordSync(password, admin[1])) {
      return res.json({ ok: false, error: '密码错误' });
    }
    // 如果是旧版 Base64 密码，自动升级为 bcrypt
    if (!isBcryptHash(admin[1])) {
      upgradePasswordToBcrypt('admin', password);
    }
    const token = signToken({ username: 'admin', role: 'admin', ts: Date.now() });
    res.json({ ok: true, token });
  } catch(e) {
    res.json({ ok: false, error: '登录失败: ' + e.message });
  }
});

// 修改管理员密码
app.post('/api/admin/change-pwd', requireAdmin, (req, res) => {
  const { oldPwd, newPwd } = req.body;
  if (!newPwd || newPwd.length < 6) {
    return res.json({ ok: false, error: '新密码至少6位' });
  }
  try {
    const result = db.exec("SELECT password FROM users WHERE username='admin'");
    if (!result.length || !result[0].values.length) {
      return res.json({ ok: false, error: '管理员账号不存在' });
    }
    const storedHash = result[0].values[0][0];
    if (!verifyPasswordSync(oldPwd, storedHash)) {
      return res.json({ ok: false, error: '原密码错误' });
    }
    db.run("UPDATE users SET password=? WHERE username=?", [hashPasswordSync(newPwd), 'admin']);
    saveDB();
    res.json({ ok: true });
  } catch(e) {
    res.json({ ok: false, error: '修改失败: ' + e.message });
  }
});

// 获取用户列表
app.get('/api/admin/users', requireAdmin, (req, res) => {
  try {
    const result = db.exec("SELECT username, email, credits, role, ref_code, created_at FROM users ORDER BY created_at DESC");
    const users = result.length ? result[0].values.map(r => ({
      username: r[0], email: r[1], credits: r[2], role: r[3], refCode: r[4], createdAt: r[5]
    })) : [];
    const total = users.length;
    const totalCredits = users.reduce((s, u) => s + u.credits, 0);
    res.json({ ok: true, users, total, totalCredits });
  } catch(e) {
    res.json({ ok: false, error: e.message });
  }
});

// 手动充值积分
app.post('/api/admin/recharge', requireAdmin, (req, res) => {
  const { username, amount, reason } = req.body;
  if (!username || !amount || amount <= 0) {
    return res.json({ ok: false, error: '请填写正确的用户名和金额' });
  }
  try {
    const user = db.exec("SELECT credits FROM users WHERE username=?", [username]);
    if (!user.length || !user[0].values.length) {
      return res.json({ ok: false, error: '用户不存在' });
    }
    db.run("UPDATE users SET credits=credits+? WHERE username=?", [amount, username]);
    db.run("INSERT INTO credit_log (username, amount, reason, admin) VALUES (?,?,?,?)",
      [username, amount, reason || '手动充值', req.adminUser]);
    saveDB();
    const newCredits = db.exec("SELECT credits FROM users WHERE username=?", [username]);
    res.json({ ok: true, username, added: amount, credits: newCredits[0].values[0][0] });
  } catch(e) {
    res.json({ ok: false, error: '充值失败: ' + e.message });
  }
});

// 充值记录
app.get('/api/admin/recharge-log', requireAdmin, (req, res) => {
  try {
    const result = db.exec("SELECT username, amount, reason, admin, created_at FROM credit_log ORDER BY created_at DESC LIMIT 200");
    const logs = result.length ? result[0].values.map(r => ({
      username: r[0], amount: r[1], reason: r[2], admin: r[3], createdAt: r[4]
    })) : [];
    res.json({ ok: true, logs });
  } catch(e) {
    res.json({ ok: false, error: e.message });
  }
});

// 获取用户信息
app.get('/api/user/data', (req, res) => {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) return res.json({ ok: false, error: '未登录' });
  try {
    const payload = JSON.parse(Buffer.from(auth.slice(7), 'base64').toString());
    const result = db.exec("SELECT username, email, credits, role, ref_code FROM users WHERE username=?", [payload.username]);
    if (!result.length || !result[0].values.length) return res.json({ ok: false, error: '用户不存在' });
    const u = result[0].values[0];
    res.json({ ok: true, data: { username: u[0], email: u[1], credits: u[2], role: u[3], refCode: u[4] } });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// Key 配置存储（服务器端）
app.get('/api/admin/keys', requireAdmin, (req, res) => {
  try {
    const result = db.exec("SELECT id, platform, prefix, models, manage_url, notes FROM key_config ORDER BY id");
    const keys = result.length ? result[0].values.map(r => ({
      id: r[0], platform: r[1], prefix: r[2], models: JSON.parse(r[3] || '[]'), manageUrl: r[4], notes: r[5]
    })) : [];
    res.json({ ok: true, keys });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

app.post('/api/admin/keys', requireAdmin, (req, res) => {
  const { platform, prefix, models, manageUrl, notes } = req.body;
  if (!platform || !prefix) return res.json({ ok: false, error: '平台名称和Key前缀必填' });
  try {
    db.run("INSERT INTO key_config (platform, prefix, models, manage_url, notes) VALUES (?,?,?,?,?)",
      [platform, prefix, JSON.stringify(models || []), manageUrl || '', notes || '']);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

app.delete('/api/admin/keys/:id', requireAdmin, (req, res) => {
  try {
    db.run("DELETE FROM key_config WHERE id=?", [req.params.id]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// ============================================================
// 知识库 API (RAG 核心)
// ============================================================

// 获取全部知识库条目
app.get('/api/knowledge', (req, res) => {
  try {
    const category = req.query.category || '';
    let sql = 'SELECT id, title, content, category, tags, source, created_at, updated_at FROM knowledge_base';
    let params = [];
    if (category) { sql += ' WHERE category=?'; params.push(category); }
    sql += ' ORDER BY updated_at DESC';
    const result = db.exec(sql, params);
    const items = result.length ? result[0].values.map(r => ({
      id: r[0], title: r[1], content: r[2], category: r[3], tags: r[4], source: r[5],
      createdAt: r[6], updatedAt: r[7]
    })) : [];
    // 同时返回分类列表
    const catResult = db.exec('SELECT DISTINCT category FROM knowledge_base ORDER BY category');
    const categories = catResult.length ? catResult[0].values.map(r => r[0]) : [];
    res.json({ ok: true, items, categories, total: items.length });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 获取单条知识
app.get('/api/knowledge/:id', (req, res) => {
  try {
    const result = db.exec('SELECT id, title, content, category, tags, source, created_at, updated_at FROM knowledge_base WHERE id=?', [req.params.id]);
    if (!result.length || !result[0].values.length) return res.json({ ok: false, error: '不存在' });
    const r = result[0].values[0];
    res.json({ ok: true, item: { id: r[0], title: r[1], content: r[2], category: r[3], tags: r[4], source: r[5], createdAt: r[6], updatedAt: r[7] } });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 新增知识
app.post('/api/knowledge', (req, res) => {
  const { title, content, category, tags, source } = req.body;
  if (!title || !content) return res.json({ ok: false, error: '标题和内容必填' });
  try {
    db.run('INSERT INTO knowledge_base (title, content, category, tags, source) VALUES (?,?,?,?,?)',
      [title, content, category || 'general', tags || '', source || '']);
    saveDB();
    const id = db.exec('SELECT last_insert_rowid()')[0].values[0][0];
    res.json({ ok: true, id });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 更新知识
app.put('/api/knowledge/:id', (req, res) => {
  const { title, content, category, tags, source } = req.body;
  try {
    db.run(`UPDATE knowledge_base SET title=?, content=?, category=?, tags=?, source=?, updated_at=datetime('now','localtime') WHERE id=?`,
      [title, content, category || 'general', tags || '', source || '', req.params.id]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 删除知识
app.delete('/api/knowledge/:id', (req, res) => {
  try {
    db.run('DELETE FROM knowledge_base WHERE id=?', [req.params.id]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// RAG 检索：基于关键词匹配 + TF-IDF 风格打分
app.post('/api/knowledge/search', (req, res) => {
  const { query, topK } = req.body;
  if (!query) return res.json({ ok: false, error: '缺少 query', results: [] });
  const k = Math.min(topK || 5, 10);

  try {
    // 拉取全部知识库条目
    const result = db.exec('SELECT id, title, content, category, tags FROM knowledge_base');
    if (!result.length || !result[0].values.length) {
      return res.json({ ok: true, results: [], query });
    }

    const items = result[0].values.map(r => ({
      id: r[0], title: r[1], content: r[2], category: r[3], tags: r[4]
    }));

    // === TF-IDF 风格关键词匹配打分 ===
    // 1. 分词：中英文混合（中文按字符 n-gram，英文按空格）
    function tokenize(text) {
      const tokens = [];
      // 提取英文单词
      const enWords = text.toLowerCase().match(/[a-zA-Z0-9_]+/g) || [];
      tokens.push(...enWords);
      // 中文：取 1-gram 和 2-gram
      const cnChars = text.replace(/[a-zA-Z0-9_\s]+/g, '');
      for (let i = 0; i < cnChars.length; i++) {
        tokens.push(cnChars[i]);
        if (i < cnChars.length - 1) tokens.push(cnChars[i] + cnChars[i + 1]);
      }
      return tokens;
    }

    // 2. 计算 IDF（简化：稀有词权重高）
    const totalDocs = items.length;
    const queryTokens = tokenize(query);
    const queryTokenSet = new Set(queryTokens);

    // 为每个文档打分
    const scored = items.map(item => {
      const docText = `${item.title} ${item.tags} ${item.content}`;
      const docTokens = tokenize(docText);
      const docTokenSet = new Set(docTokens);

      let score = 0;
      for (const qt of queryTokenSet) {
        // TF in query
        const queryTF = queryTokens.filter(t => t === qt).length;
        if (docTokenSet.has(qt)) {
          // 计算 IDF：包含这个词的文档数
          const docsWithTerm = items.filter(i => {
            const t = `${i.title} ${i.tags} ${i.content}`;
            return tokenize(t).includes(qt);
          }).length;
          const idf = Math.log((totalDocs + 1) / (docsWithTerm + 1)) + 1;
          // TF in doc
          const docTF = docTokens.filter(t => t === qt).length;
          score += queryTF * docTF * idf;
        }
      }

      // 标题命中加权
      const titleLower = item.title.toLowerCase();
      for (const qt of queryTokenSet) {
        if (titleLower.includes(qt)) score *= 2.5;
      }

      return { ...item, score };
    });

    // 排序取 topK，过滤掉得分为 0 的
    const results = scored
      .filter(s => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, k)
      .map(s => ({
        id: s.id,
        title: s.title,
        content: s.content,
        category: s.category,
        score: Math.round(s.score * 100) / 100
      }));

    res.json({ ok: true, results, query, total: items.length, matched: results.length });
  } catch(e) {
    res.json({ ok: false, error: e.message, results: [] });
  }
});

// ============================================================
// 自定义错误页面
// ============================================================
const err404HTML = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>404 - Nexus Hub</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f8f7ff;color:#1a1035;text-align:center}.wrap{max-width:500px;padding:40px}h1{font-size:80px;font-weight:800;background:linear-gradient(135deg,#6c4ef5,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2}p{font-size:18px;color:#6b5b95;margin:16px 0 24px}a{display:inline-block;padding:12px 28px;background:linear-gradient(135deg,#6c4ef5,#a855f7);color:#fff;border-radius:10px;text-decoration:none;font-weight:600}</style></head><body><div class="wrap"><h1>404</h1><p>页面不存在或已移动</p><a href="/">返回首页</a></div></body></html>`;
const err500HTML = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>500 - Nexus Hub</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f8f7ff;color:#1a1035;text-align:center}.wrap{max-width:500px;padding:40px}h1{font-size:80px;font-weight:800;background:linear-gradient(135deg,#ef4444,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2}p{font-size:18px;color:#6b5b95;margin:16px 0 24px}a{display:inline-block;padding:12px 28px;background:linear-gradient(135deg,#6c4ef5,#a855f7);color:#fff;border-radius:10px;text-decoration:none;font-weight:600}</style></head><body><div class="wrap"><h1>500</h1><p>服务器内部错误，请稍后重试</p><a href="/">返回首页</a></div></body></html>`;


// ============================================================
// AI 小说 API（角色卡片/世界观/章节/版本管理）
// ============================================================
// 获取用户作品列表
app.get('/api/novels', authRequired, (req, res) => {
  try {
    var result = db.exec("SELECT id, username, title, type, outline, core, total_words, chapter_count, status, created_at, updated_at FROM novels WHERE username=? ORDER BY updated_at DESC", [req.user.username]);
    res.json({ ok: true, novels: result.length && result[0].values.length ? result[0].values.map(v => ({ id: v[0], title: v[2], type: v[3], total_words: v[6], chapter_count: v[7], status: v[8], updated_at: v[10] })) : [] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 创建作品
app.post('/api/novels', authRequired, (req, res) => {
  try {
    var { title, type, core } = req.body;
    db.run("INSERT INTO novels (username, title, type, core) VALUES (?,?,?,?)", [req.user.username, title || '未命名作品', type || '', core || '']);
    saveDB();
    var id = db.exec("SELECT last_insert_rowid()");
    res.json({ ok: true, novel_id: id[0].values[0][0] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 获取作品详情（含角色+世界观）
app.get('/api/novels/:id', authRequired, (req, res) => {
  try {
    var nv = db.exec("SELECT * FROM novels WHERE id=? AND username=?", [req.params.id, req.user.username]);
    if (!nv.length || !nv[0].values.length) return res.json({ ok: false, error: '作品不存在' });
    var v = nv[0].values[0];
    var chars = db.exec("SELECT * FROM novel_characters WHERE novel_id=?", [req.params.id]);
    var worlds = db.exec("SELECT * FROM novel_worlds WHERE novel_id=?", [req.params.id]);
    res.json({ ok: true, novel: { id: v[0], title: v[3], type: v[4], outline: v[5], core: v[6], total_words: v[7], chapter_count: v[8], status: v[9] }, characters: chars.length ? chars[0].values.map(r => ({ id: r[0], name: r[3], gender: r[5], age: r[6], appearance: r[7], personality: r[8], background: r[9], goal: r[10], arc: r[11], notes: r[12] })) : [], worlds: worlds.length ? worlds[0].values.map(r => ({ id: r[0], category: r[4], key: r[5], value: r[6] })) : [] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 更新作品
app.put('/api/novels/:id', authRequired, (req, res) => {
  try {
    var { title, type, outline, core } = req.body;
    if (title !== undefined) db.run("UPDATE novels SET title=? WHERE id=? AND username=?", [title, req.params.id, req.user.username]);
    if (type !== undefined) db.run("UPDATE novels SET type=? WHERE id=? AND username=?", [type, req.params.id, req.user.username]);
    if (outline !== undefined) db.run("UPDATE novels SET outline=? WHERE id=? AND username=?", [outline, req.params.id, req.user.username]);
    if (core !== undefined) db.run("UPDATE novels SET core=? WHERE id=? AND username=?", [core, req.params.id, req.user.username]);
    db.run("UPDATE novels SET updated_at=datetime('now','localtime') WHERE id=?", [req.params.id]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 角色卡片 CRUD
app.get('/api/novels/:id/characters', authRequired, (req, res) => {
  try {
    var chars = db.exec("SELECT * FROM novel_characters WHERE novel_id=? ORDER BY id", [req.params.id]);
    res.json({ ok: true, characters: chars.length ? chars[0].values.map(r => ({ id: r[0], name: r[3], gender: r[5], age: r[6], appearance: r[7], personality: r[8], background: r[9], goal: r[10], arc: r[11], notes: r[12] })) : [] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.post('/api/novels/:id/characters', authRequired, (req, res) => {
  try {
    var { name, gender, age, appearance, personality, background, goal, arc, notes } = req.body;
    db.run("INSERT INTO novel_characters (username, novel_id, name, gender, age, appearance, personality, background, goal, arc, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", [req.user.username, req.params.id, name || '新角色', gender || '', age || '', appearance || '', personality || '', background || '', goal || '', arc || '', notes || '']);
    saveDB();
    res.json({ ok: true, character_id: db.exec("SELECT last_insert_rowid()")[0].values[0][0] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.put('/api/characters/:id', authRequired, (req, res) => {
  try {
    var fields = req.body;
    Object.keys(fields).forEach(function(k) { db.run("UPDATE novel_characters SET " + k + "=? WHERE id=?", [fields[k], req.params.id]); });
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.delete('/api/characters/:id', authRequired, (req, res) => {
  try { db.run("DELETE FROM novel_characters WHERE id=?", [req.params.id]); saveDB(); res.json({ ok: true }); } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 世界观设定
app.post('/api/novels/:id/worlds', authRequired, (req, res) => {
  try {
    var { category, key, value } = req.body;
    db.run("INSERT INTO novel_worlds (username, novel_id, category, key, value) VALUES (?,?,?,?,?)", [req.user.username, req.params.id, category || 'general', key || '', value || '']);
    saveDB();
    res.json({ ok: true, world_id: db.exec("SELECT last_insert_rowid()")[0].values[0][0] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.delete('/api/worlds/:id', authRequired, (req, res) => {
  try { db.run("DELETE FROM novel_worlds WHERE id=?", [req.params.id]); saveDB(); res.json({ ok: true }); } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 章节管理（含版本自动保存）
app.get('/api/novels/:id/chapters', authRequired, (req, res) => {
  try {
    var chaps = db.exec("SELECT * FROM novel_chapters WHERE novel_id=? ORDER BY chapter_index", [req.params.id]);
    res.json({ ok: true, chapters: chaps.length ? chaps[0].values.map(r => ({ id: r[0], index: r[4], title: r[5], content: r[6], outline: r[7], word_count: r[8] })) : [] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.post('/api/novels/:id/chapters', authRequired, (req, res) => {
  try {
    var { title, content, outline, chapter_index } = req.body;
    db.run("INSERT INTO novel_chapters (username, novel_id, chapter_index, title, content, outline, word_count) VALUES (?,?,?,?,?,?,?)", [req.user.username, req.params.id, chapter_index || 0, title || '', content || '', outline || '', (content || '').length]);
    saveDB();
    res.json({ ok: true, chapter_id: db.exec("SELECT last_insert_rowid()")[0].values[0][0] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.put('/api/chapters/:id', authRequired, (req, res) => {
  try {
    var { title, content, outline } = req.body;
    if (content !== undefined) {
      db.run("UPDATE novel_chapters SET content=?, word_count=? WHERE id=?", [content, content.length, req.params.id]);
      db.run("INSERT INTO novel_chapter_versions (chapter_id, username, version, content, summary) VALUES (?,(SELECT COALESCE(MAX(version),0)+1 FROM novel_chapter_versions WHERE chapter_id=?)),?)", [req.params.id, req.user.username, req.params.id, content, title || '']);
    }
    if (title !== undefined) db.run("UPDATE novel_chapters SET title=? WHERE id=?", [title, req.params.id]);
    if (outline !== undefined) db.run("UPDATE novel_chapters SET outline=? WHERE id=?", [outline, req.params.id]);
    db.run("UPDATE novel_chapters SET updated_at=datetime('now','localtime') WHERE id=?", [req.params.id]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 版本历史
app.get('/api/chapters/:id/versions', authRequired, (req, res) => {
  try {
    var vers = db.exec("SELECT * FROM novel_chapter_versions WHERE chapter_id=? ORDER BY version DESC", [req.params.id]);
    res.json({ ok: true, versions: vers.length ? vers[0].values.map(r => ({ id: r[0], version: r[3], content: r[4], summary: r[5], created_at: r[6] })) : [] });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});
app.delete('/api/chapters/:id', authRequired, (req, res) => {
  try { db.run("DELETE FROM novel_chapters WHERE id=?", [req.params.id]); db.run("DELETE FROM novel_chapter_versions WHERE chapter_id=?", [req.params.id]); saveDB(); res.json({ ok: true }); } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 导出 TXT
app.get('/api/novels/:id/export', authRequired, (req, res) => {
  try {
    var nv = db.exec("SELECT * FROM novels WHERE id=? AND username=?", [req.params.id, req.user.username]);
    if (!nv.length || !nv[0].values.length) return res.status(404).json({ ok: false, error: '作品不存在' });
    var v = nv[0].values[0];
    var chaps = db.exec("SELECT * FROM novel_chapters WHERE novel_id=? ORDER BY chapter_index", [req.params.id]);
    var text = '《' + v[3] + '》\n\n';
    if (chaps.length && chaps[0].values.length) { chaps[0].values.forEach(function(ch, i) { text += '第' + (i+1) + '章 ' + (ch[5]||'') + '\n\n' + (ch[6]||'') + '\n\n'; }); }
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="' + v[3] + '.txt"');
    res.send(text);
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 删除作品（级联删除依赖数据）
app.delete('/api/novels/:id', authRequired, (req, res) => {
  try {
    var nid = req.params.id;
    db.run("DELETE FROM novels WHERE id=? AND username=?", [nid, req.user.username]);
    db.run("DELETE FROM novel_characters WHERE novel_id=?", [nid]);
    db.run("DELETE FROM novel_worlds WHERE novel_id=?", [nid]);
    var chs = db.exec("SELECT id FROM novel_chapters WHERE novel_id=?", [nid]);
    if (chs.length && chs[0].values.length) { chs[0].values.forEach(function(ch) { db.run("DELETE FROM novel_chapter_versions WHERE chapter_id=?", [ch[0]]); }); }
    db.run("DELETE FROM novel_chapters WHERE novel_id=?", [nid]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// ============================================================
// 简易访问统计
// ============================================================
let statsData = { pv: 0, uv: new Set(), today: new Date().toDateString() };
app.use((req, res, next) => {
  const now = new Date().toDateString();
  if (now !== statsData.today) { statsData = { pv: 0, uv: new Set(), today: now }; }
  statsData.pv++;
  const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || '';
  if (ip) statsData.uv.add(ip);
  next();
});
app.get('/api/stats', (req, res) => {
  res.json({ pv: statsData.pv, uv: statsData.uv.size, today: statsData.today });
});

// ============================================================
// 启动服务
// ============================================================
// 管理员认证（服务端存储密码，跨浏览器/缓存后不丢失）
// ============================================================
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin123';
app.post('/api/admin/auth', authLimiter, (req, res) => {

// ============================================================
// 会员体系
// ============================================================
const FREE_ALWAYS = ['dmx_qwen35_2b_free', 'dmx_qwen3_17b_free', 'dmx_spark_lite_free', 'dmx_glm_4_9b', 'ark_dbs2_mini', 'ark_dbp15l', 'qf_ernie_speed']; // 始终免费
const MEMBERSHIP_TIERS = {
  free:  { name: '免费用户', dailyFreeCalls: 30, discount: 0, price: 0, creditsPerMonth: 0, desc: '基础体验' },
  silver:{ name: '月度会员', dailyFreeCalls: 999, discount: 0.2, price: 49, creditsPerMonth: 1000, desc: '高端模型8折' },
  gold:  { name: '季度会员', dailyFreeCalls: 999, discount: 0.3, price: 119, creditsPerMonth: 3500, desc: '高端模型7折+返利5%' },
  platinum:{name: '年度会员', dailyFreeCalls: 999, discount: 0.5, price: 369, creditsPerMonth: 15000, desc: '高端模型5折+返利10%+3D五折' },
};
function getMembership(user) {
  if (!user) return MEMBERSHIP_TIERS.free;
  const tier = user.membership || 'free';
  const expires = user.membership_expires || '';
  if (tier !== 'free' && expires && new Date(expires) < new Date()) return MEMBERSHIP_TIERS.free; // 过期降级
  return MEMBERSHIP_TIERS[tier] || MEMBERSHIP_TIERS.free;
}

// 查看会员状态
app.get('/api/membership/status', authRequired, (req, res) => {
  const result = db.exec("SELECT membership, membership_expires, daily_free_usage, daily_free_date, credits FROM users WHERE username=?", [req.user.username]);
  if (!result.length || !result[0].values.length) return res.json({ ok: false, error: '用户不存在' });
  const u = result[0].values[0];
  const tier = getMembership({ membership: u[0], membership_expires: u[1] });
  res.json({
    ok: true,
    membership: u[0],
    expires: u[1] || '',
    tierName: tier.name,
    dailyFreeCalls: tier.dailyFreeCalls,
    discount: tier.discount,
    dailyFreeUsed: u[2] || 0,
    dailyFreeDate: u[3] || '',
    credits: u[4] || 0,
  });
});

// 订阅会员（记录在数据库中，实际支付待接入）
app.post('/api/membership/subscribe', authRequired, (req, res) => {
  const { tier, months } = req.body;
  if (!MEMBERSHIP_TIERS[tier]) return res.json({ ok: false, error: '无效的会员等级' });
  if (tier === 'free') return res.json({ ok: false, error: '已经是免费用户' });
  const m = MEMBERSHIP_TIERS[tier];
  // 计算到期时间
  const now = new Date();
  const currentResult = db.exec("SELECT membership_expires FROM users WHERE username=?", [req.user.username]);
  let baseDate = now;
  if (currentResult.length && currentResult[0].values.length && currentResult[0].values[0][0]) {
    const existing = new Date(currentResult[0].values[0][0]);
    if (existing > now) baseDate = existing; // 续期叠加
  }
  const expireDate = new Date(baseDate);
  expireDate.setMonth(expireDate.getMonth() + (months || 1));
  const totalPrice = m.price * (months || 1);
  // 这里实际应接入支付，现在先直接记录
  db.run("UPDATE users SET membership=?, membership_expires=?, credits=credits+? WHERE username=?", 
    [tier, expireDate.toISOString(), m.creditsPerMonth * (months || 1), req.user.username]);
  saveDB();
  res.json({ ok: true, tier, expires: expireDate.toISOString(), creditsAdded: m.creditsPerMonth * (months || 1), price: totalPrice });
});
  const { password } = req.body || {};
  if (password === ADMIN_PASSWORD) {
    res.json({ ok: true, token: Buffer.from(password + ':' + Date.now()).toString('base64') });
  } else {
    res.json({ ok: false, error: '密码错误' });
  }
});

// ============================================================
// API Key 管理系统 — 用户生成自己的 Key 接入外部应用
// ============================================================
function generateApiKey(prefix) {
  return 'ai-' + (prefix || 'nx') + '-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 8);
}

// 创建 API Key
app.post('/api/keys/create', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  try {
    const payload = verifyToken(token);
    const username = payload.username;
    const keyName = (req.body.name || '').trim() || '默认 Key';
    const apiKey = generateApiKey(username.substring(0, 3));
    db.run("INSERT INTO api_keys (username, key_name, api_key, quota) VALUES (?,?,?,?)",
      [username, keyName, apiKey, 0]);
    saveDB();
    res.json({ ok: true, apiKey, name: keyName });
  } catch(e) { res.json({ ok: false, error: '创建失败: ' + e.message }); }
});

// 获取我的 API Keys
app.get('/api/keys', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  try {
    const payload = verifyToken(token);
    const result = db.exec("SELECT id, key_name, api_key, quota, used, active, created_at FROM api_keys WHERE username=? ORDER BY id DESC",
      [payload.username]);
    const keys = result.length ? result[0].values.map(v => ({
      id: v[0], name: v[1], key: v[2], quota: v[3], used: v[4], active: v[5], created: v[6]
    })) : [];
    res.json({ ok: true, keys });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// 删除 API Key
app.delete('/api/keys/:id', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  try {
    const payload = verifyToken(token);
    db.run("DELETE FROM api_keys WHERE id=? AND username=?", [req.params.id, payload.username]);
    saveDB();
    res.json({ ok: true });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

// ============================================================
// OpenAI 兼容代理 — 用户用自己的 Key 调用 Nexus Hub 模型
// POST /v1/chat/completions
// ============================================================
app.post('/v1/chat/completions', async (req, res) => {
  const apiKey = (req.headers.authorization || '').replace('Bearer ', '');
  if (!apiKey) return res.status(401).json({ error: { message: '缺少 API Key', type: 'auth_error' } });
  
  // 查找 Key
  const result = db.exec("SELECT a.username, a.quota, a.used, a.active, u.credits FROM api_keys a JOIN users u ON a.username=u.username WHERE a.api_key=?",
    [apiKey]);
  if (!result.length || !result[0].values.length) {
    return res.status(401).json({ error: { message: '无效的 API Key', type: 'auth_error' } });
  }
  const keyInfo = result[0].values[0];
  if (!keyInfo[3]) { // not active
    return res.status(403).json({ error: { message: 'API Key 已被禁用', type: 'auth_error' } });
  }
  
  const username = keyInfo[0];
  const { model, messages } = req.body;
  if (!model || !messages) return res.status(400).json({ error: { message: '缺少 model 或 messages 参数' } });
  
  // 查找模型配置
  const config = MODEL_CONFIG[model];
  if (!config) return res.status(400).json({ error: { message: `不支持的模型: ${model}`, type: 'invalid_request_error' } });
  
  // 计算成本 — 和前端 MODEL_COST 保持一致
  const modelCostMap = {
    dmx_qwen35_2b_free:0, dmx_qwen3_17b_free:0, dmx_spark_lite_free:0,
    sf_qwen3_8b:0, sf_deepseek_v3_free:0, dmx_qwen3_8b_free:0, dmx_qwen_flash_free:0,
    deepseekv3:1, glm4:1, kimi:1, sf_glm47:0, ali_qwen36_flash:1,
    dmx_minimax_m25_free:0, dmx_glm_47_free:0, dmx_glm_47_flash:0, dmx_glm_45_flash:0,
    dmx_glm_4_9b:0, dmx_hunyuan_lite:0, dmx_qwen35_plus_free:0,
    dmx_qwen3_5_plus_free:0, dmx_qwen35_35b_free:0, dmx_qwen25_coder_7b:0,
    dmx_doubao_seed_lite:0, dmx_mimo_v25_free:0, sf_qwen3_32b:0, or_codeqwen:1,
    glm4plus:1, minimax:1, spark4:1, ali_qwen36_plus:1, ali_deepseek_v4_flash:1,
    // 硅基流动免费模型（以上已归零）
    sf_hunyuan_a13b:1, sf_qwen35_397b:1, sf_qwq_32b:1,
    // DMXAPI 全免费模型
    dmx_minimax_m27_free:0, dmx_minimax_m25_free:0,
    dmx_glm_47_free:0, dmx_glm_47_flash:0, dmx_glm_5_free:0, dmx_glm_51_free:0,
    dmx_glm_5_turbo_free:0, dmx_glm_45_flash:0, dmx_glm_4_9b:0,
    dmx_hunyuan_lite:0, dmx_qwen3_8b_free:0, dmx_qwen_flash_free:0,
    dmx_qwen3_5_plus_free:0, dmx_qwen35_plus_free:0,
    dmx_qwen3_coder_plus_free:0, dmx_qwen3_coder_next_free:0,
    dmx_doubao_seed_code:0, dmx_mimo_v2_pro_free:0, dmx_mimo_v25_free:0,
    dmx_code_free:0, dmx_codex_free:0, dmx_kat_coder_free:0,
    dmx_qwen36_plus_free:0, dmx_code_free_x:0,
    dmx_kimi_k25_free:0, dmx_kimi_k26_free:0, dmx_doubao_seed_pro:0, dmx_qwen3_max_free:0,
    ark_dbs2_mini:0, ark_dbp15l:0, ark_dbs2_lite:0,
    ark_dsv4f:0, ark_dbs1_6:0, ark_dbs1_8:0, ark_dbs_code:0,
    ark_dsv32:0, ark_dsv4p:0, ark_dbs2_pro:0, ark_glm47:0,
    ark_dbp15p:0, ark_dbs_char:0,
    // API Nexus 海外旗舰（降价70%，目标毛利率70%）
    nx_gpt5:8, nx_gpt5mini:3, nx_gpt5chat:5, nx_gpt5nano:2, nx_gpt5all:8,
    nx_gpt51chat:6, nx_gpt51codex:8, nx_gpt51codexmax:10,
    nx_gpt52chat:8, nx_gpt52pro:8,
    nx_gpt53chat:8, nx_gpt53codex:12,
    nx_gpt54pro:12, nx_gpt54mini:5, nx_gpt54nano:3,
    nx_gpt55pro:15, nx_gpt55:15,
  nx_claude_opus:12, nx_claude_sonnet:6,
  nx_claude_haiku:5, nx_gemini_pro:6, nx_o3mini:5,
  nx_dalle3:8, nx_flux:5, nx_suno:8, nx_grok3:8,
    meshy_text:288, meshy_image:288,
    qf_ernie4:5, qf_ernie35:2, qf_ernie_speed:0,
    ark_doubao_pro:0, ark_doubao_lite:0,
    bc_baichuan4:2, bc_baichuan3:1,
    qwen3:2, kimi2:2, minimax1:2, doubao:2, doubao15:2, gpt4omini:2, gemini15flash:2,
    ali_qwen37_max:8, ali_deepseek_v4_pro:2, ali_kimi_k26:2,
    sf_deepseek_v32:1, sf_glm5:2,
    deepseekr1:5, gpt4o:5, hunyuan:5, gemini15pro:5, gemini25flash:5,
    grok3:5, ali_glm51:5, 'mistral-large2':5,
    or_llama3_70b:5, or_mistral_large:5, or_perplexity:5, llama4:3,
    gpt4turbo:10, claude35:10, claude3opus:10, claude4:10,
    gemini25pro:10,
    or_gpt4o:10, or_claude_sonnet:10, or_gemini25pro:10,
    qiniu_claude37:10, qiniu_claudeopus4:10, qiniu_gpt4o:10, qiniu_o3:10,
    qiniu_gemini25pro:10,
    claude4opus:15,
  };
  let creditCost = modelCostMap[model] || 2;
  // 检查积分
  const userCredits = keyInfo[4] || 0;
  if (userCredits < creditCost) {
    return res.status(402).json({ error: { message: '积分不足，请充值', type: 'insufficient_credits' } });
  }
  
  // 扣积分
  db.run("UPDATE users SET credits=credits-? WHERE username=?", [creditCost, username]);
  db.run("UPDATE api_keys SET used=used+? WHERE api_key=?", [creditCost, apiKey]);
  db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)", [username, -creditCost, 'API调用: '+model]);
  saveDB();
  
  // 调用模型
  try {
    const apiKeyVal = getApiKey(config.provider, model);
    if (!apiKeyVal) return res.status(500).json({ error: { message: '平台配置错误' } });
    
    // 高成本模型 token 上限控制（防止单次调用消耗过大）
    const MAX_TOKENS_MAP = {
      nx_gpt5: 2048, nx_gpt5all: 2048, nx_gpt54pro: 2048, nx_gpt55pro: 2048, nx_gpt55: 2048,
      nx_gpt52pro: 2048, nx_gpt53codex: 2048,
      nx_claude_opus: 2048, nx_claude_sonnet: 4096,
      nx_gemini_pro: 4096, nx_grok3: 4096, nx_o3mini: 4096,
      nx_gpt5mini: 4096, nx_claude_haiku: 4096,
      ali_qwen37_max: 4096,
    };
    const tokenCap = MAX_TOKENS_MAP[model];
    const userMaxTokens = req.body.max_tokens || 4096;
    const effectiveMaxTokens = tokenCap ? Math.min(userMaxTokens, tokenCap) : userMaxTokens;
    
    const url = `${config.baseUrl}/chat/completions`;
    const body = JSON.stringify({
      model: config.model,
      messages,
      stream: false,
      temperature: req.body.temperature || 0.7,
      max_tokens: effectiveMaxTokens,
    });
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKeyVal}` },
      body,
    });
    const data = await response.json();
    
    // 注入使用信息
    data._credits_used = creditCost;
    data._credits_remaining = userCredits - creditCost;
    res.json(data);
  } catch(e) {
    // 调用失败退款
    db.run("UPDATE users SET credits=credits+? WHERE username=?", [creditCost, username]);
    db.run("UPDATE api_keys SET used=used-? WHERE api_key=?", [creditCost, apiKey]);
    saveDB();
    res.status(500).json({ error: { message: 'Nexus Hub 模型调用失败: ' + e.message, type: 'api_error' } });
  }
});

// 获取所有可用模型（供API Key用户参考）
app.get('/v1/models', (req, res) => {
  const apiKey = (req.headers.authorization || '').replace('Bearer ', '');
  if (!apiKey) return res.status(401).json({ error: { message: '缺少 API Key' } });
  const result = db.exec("SELECT id FROM api_keys WHERE api_key=? AND active=1", [apiKey]);
  if (!result.length || !result[0].values.length) return res.status(401).json({ error: { message: '无效的 API Key' } });
  
  const models = Object.entries(MODEL_CONFIG).map(([id, config]) => ({
    id, object: 'model', owned_by: 'nexus-hub'
  }));
  res.json({ object: 'list', data: models });
});

// ============================================================
// 忘记密码 — 通过密保问题重置
// ============================================================
// 用户修改资料
app.post('/api/user/update-profile', (req, res) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.json({ ok: false, error: '未登录' });
  try {
    const payload = verifyToken(token);
    const { email, oldPassword, newPassword } = req.body;
    const user = db.exec("SELECT password FROM users WHERE username=?", [payload.username]);
    if (!user.length || !user[0].values.length) return res.json({ ok: false, error: '用户不存在' });
    if (user[0].values[0][0] !== oldPassword) return res.json({ ok: false, error: '当前密码错误' });
    if (email) db.run("UPDATE users SET email=? WHERE username=?", [email, payload.username]);
    if (newPassword) db.run("UPDATE users SET password=? WHERE username=?", [newPassword, payload.username]);
    saveDB();
    res.json({ ok: true, message: '已保存' });
  } catch(e) { res.json({ ok: false, error: e.message }); }
});

app.post('/api/auth/forgot-password', authLimiter, (req, res) => {
  const { phone, securityAnswer, newPassword } = req.body;
  if (!phone || !securityAnswer || !newPassword) {
    return res.json({ ok: false, error: '请填写完整信息' });
  }
  if (newPassword.length < 6) {
    return res.json({ ok: false, error: '新密码至少6位' });
  }
  try {
    const result = db.exec("SELECT username, security_a FROM users WHERE phone=?", [phone]);
    if (!result.length || !result[0].values.length) {
      return res.json({ ok: false, error: '未找到该手机号关联的账号' });
    }
    const user = result[0].values[0];
    const storedAnswer = user[1];
    if (!storedAnswer) {
      return res.json({ ok: false, error: '该账号未设置密保，无法找回' });
    }
    if (!verifyPasswordSync(securityAnswer, storedAnswer)) {
      return res.json({ ok: false, error: '密保答案错误' });
    }
    db.run("UPDATE users SET password=? WHERE phone=?", [hashPasswordSync(newPassword), phone]);
    saveDB();
    res.json({ ok: true, message: '密码已重置，请使用新密码登录', username: user[0] });
  } catch(e) {
    res.json({ ok: false, error: '重置失败: ' + e.message });
  }
});
// ============================================================
// 平台余额查询
// ============================================================
app.get('/api/admin/balances', async (req, res) => {
  const results = {};
  const check = async (name, url, headers, parseFn) => {
    try {
      const r = await fetch(url, { headers, signal: AbortSignal.timeout(10000) });
      if (!r.ok) return { balance: 0, unit: '元', status: 'down', error: `HTTP ${r.status}` };
      const d = await r.json();
      return parseFn ? parseFn(d) : { balance: 0, unit: '元', status: 'ok' };
    } catch(e) {
      return { balance: 0, unit: '元', status: 'down', error: e.message };
    }
  };
  // DeepSeek（支持余额查询）
  if (process.env.DEEPSEEK_API_KEY) {
    results.deepseek = await check('DeepSeek',
      'https://api.deepseek.com/user/balance',
      { Authorization: `Bearer ${process.env.DEEPSEEK_API_KEY}` },
      d => { const bal = (d.balance_infos || []).reduce((s, b) => s + parseFloat(b.total_balance || 0), 0);
             return { balance: bal.toFixed(2), unit: '元', status: bal > 1 ? 'ok' : 'low' }; }
    );
  }
  // 硅基流动（支持余额）
  if (process.env.SILICONFLOW_API_KEY) {
    results.siliconflow = await check('SiliconFlow',
      'https://api.siliconflow.cn/v1/user/info',
      { Authorization: `Bearer ${process.env.SILICONFLOW_API_KEY}` },
      d => { const bal = d.data?.balance || d.balance || 0;
             return { balance: parseFloat(bal).toFixed(2), unit: '元', status: bal > 5 ? 'ok' : 'low' }; }
    );
  }
  // OpenRouter（支持余额）
  if (process.env.OPENROUTER_API_KEY) {
    results.openrouter = await check('OpenRouter',
      'https://openrouter.ai/api/v1/auth/key',
      { Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}` },
      d => { const bal = d.data?.credits || 0;
             return { balance: parseFloat(bal).toFixed(2), unit: '$', status: bal > 0.5 ? 'ok' : 'low' }; }
    );
  }
  res.json({ ok: true, balances: results, updated: new Date().toISOString() });
});

// ============================================================
// 访客反作弊积分系统（设备指纹 + IP 限制 + 渐进式解锁）
// ============================================================
const GUEST_MAX_CREDITS = 30;       // 每个访客每日最大积分
const GUEST_PROGRESSIVE_WARN = 20;   // 使用超过 20 分后提示注册
const GUEST_REGISTER_BLOCK = 30;     // 使用 30 分后必须注册

// 获取或创建访客记录
function getOrCreateGuest(fingerprint, ip) {
  if (!fingerprint || fingerprint.length < 8) return null;
  const existing = db.exec("SELECT credits_used, daily_credits, last_reset_date FROM guest_fingerprints WHERE fingerprint=?", [fingerprint]);
  const today = new Date().toISOString().slice(0, 10);
  let record;
  if (existing.length && existing[0].values.length) {
    const r = existing[0].values[0];
    // 如果上次重置不是今天，重置每日已用积分为0
    const dailyReset = r[2] !== today;
    record = {
      credits_used: r[0],
      daily_credits: dailyReset ? 0 : (r[1] || 0),
      last_reset_date: today
    };
    if (dailyReset) {
      db.run("UPDATE guest_fingerprints SET daily_credits=0, last_reset_date=?, last_seen=datetime('now','localtime') WHERE fingerprint=?", [today, fingerprint]);
      saveDB();
    } else {
      db.run("UPDATE guest_fingerprints SET last_seen=datetime('now','localtime') WHERE fingerprint=?", [fingerprint]);
    }
  } else {
    // 新建访客记录
    db.run("INSERT INTO guest_fingerprints (fingerprint, ip, credits_used, daily_credits, last_reset_date) VALUES (?,?,0,0,?)",
      [fingerprint, ip, today]);
    saveDB();
    record = { credits_used: 0, daily_credits: 0, last_reset_date: today };
  }
  return record;
}

// 同步访客积分（前端页面加载时调用）
app.post('/api/guest/sync', (req, res) => {
  const { deviceFp } = req.body;
  const clientIP = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
  if (!deviceFp || deviceFp.length < 8) {
    // 没有设备指纹时，返回默认30分（但前端发现后会生成指纹重试）
    return res.json({ ok: true, credits: GUEST_MAX_CREDITS, max: GUEST_MAX_CREDITS, used: 0, isGuest: true });
  }
  try {
    const record = getOrCreateGuest(deviceFp, clientIP);
    if (!record) {
      return res.json({ ok: true, credits: GUEST_MAX_CREDITS, max: GUEST_MAX_CREDITS, used: 0, isGuest: true });
    }
    const remaining = Math.max(0, GUEST_MAX_CREDITS - record.daily_credits);
    // 渐进式状态
    let progressiveStatus = 'normal';
    if (record.daily_credits >= GUEST_REGISTER_BLOCK) {
      progressiveStatus = 'blocked';
    } else if (record.daily_credits >= GUEST_PROGRESSIVE_WARN) {
      progressiveStatus = 'must_register';
    } else if (record.daily_credits >= 15) {
      progressiveStatus = 'suggest_register';
    }
    res.json({
      ok: true,
      credits: remaining,
      max: GUEST_MAX_CREDITS,
      used: record.daily_credits,
      totalUsed: record.credits_used,
      progressiveStatus,
      isGuest: true
    });
  } catch(e) {
    res.json({ ok: true, credits: GUEST_MAX_CREDITS, max: GUEST_MAX_CREDITS, used: 0, isGuest: true });
  }
});

// 访客消费积分
app.post('/api/guest/spend', (req, res) => {
  const { deviceFp, amount } = req.body;
  const clientIP = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
  if (!deviceFp || deviceFp.length < 8) {
    return res.json({ ok: false, error: '设备指纹无效' });
  }
  if (!amount || amount <= 0) {
    return res.json({ ok: false, error: '金额无效' });
  }
  try {
    const record = getOrCreateGuest(deviceFp, clientIP);
    if (!record) {
      return res.json({ ok: false, error: '无法创建访客记录' });
    }
    // 检查是否已超过每日限额
    if (record.daily_credits + amount > GUEST_MAX_CREDITS) {
      const remaining = GUEST_MAX_CREDITS - record.daily_credits;
      return res.json({
        ok: false,
        error: `访客每日积分已用完（今日已用 ${record.daily_credits}/${GUEST_MAX_CREDITS}）`,
        credits: Math.max(0, remaining),
        blocked: true,
        progressiveStatus: 'blocked'
      });
    }
    db.run("UPDATE guest_fingerprints SET credits_used=credits_used+?, daily_credits=daily_credits+?, last_seen=datetime('now','localtime') WHERE fingerprint=?",
      [amount, amount, deviceFp]);
    saveDB();
    const remaining = GUEST_MAX_CREDITS - (record.daily_credits + amount);
    let progressiveStatus = 'normal';
    const newUsed = record.daily_credits + amount;
    if (newUsed >= GUEST_REGISTER_BLOCK) {
      progressiveStatus = 'blocked';
    } else if (newUsed >= GUEST_PROGRESSIVE_WARN) {
      progressiveStatus = 'must_register';
    } else if (newUsed >= 15) {
      progressiveStatus = 'suggest_register';
    }
    res.json({
      ok: true,
      credits: Math.max(0, remaining),
      used: newUsed,
      max: GUEST_MAX_CREDITS,
      progressiveStatus
    });
  } catch(e) {
    res.json({ ok: false, error: '消费失败: ' + e.message });
  }
});

// 增强注册：同一设备指纹只能注册 1 个账号
// 此逻辑集成在现有 /api/auth/register 的 IP 检查之后

// 404 处理（必须在所有路由之后）
app.use((req, res) => {
  res.status(404).type('html').send(err404HTML);
});
// 全局错误处理
app.use((err, req, res, next) => {
  console.error('Server error:', err.message);
  res.status(500).type('html').send(err500HTML);
});

// ============================================================
initDB().then(() => {
  app.listen(PORT, () => {
    console.log(`\n⚡ Nexus Hub 后端代理已启动`);
    console.log(`   本地访问: http://localhost:${PORT}`);
    console.log(`   API 状态: http://localhost:${PORT}/api/status`);
    console.log(`   数据库: ${DB_FILE}`);

    // 检查各平台 Key 配置状态（按平台分组输出）
    const platforms = {};
    const modelsWithoutKey = [];
    for (const [id, config] of Object.entries(MODEL_CONFIG)) {
      const platformKey = id.includes('_') ? id.split('_')[0] : config.provider;
      if (!platforms[platformKey]) {
        const envVar = getApiKey(config.provider, id);
        const configured = !!envVar;
        platforms[platformKey] = { configured, count: 0, hasKey: configured };
      }
      // 检查具体模型是否有 Key
      const key = getApiKey(config.provider, id);
      if (!key) {
        modelsWithoutKey.push(id);
      }
      platforms[platformKey].count++;
    }
    console.log(`\n📋 API Key 配置状态（${Object.keys(MODEL_CONFIG).length} 个模型）:`);
    for (const [name, info] of Object.entries(platforms).sort((a,b)=>a[0].localeCompare(b[0]))) {
      const icon = info.hasKey ? '✅' : '❌';
      console.log(`   ${icon} ${name.padEnd(14)} ${info.count} 个模型`);
    }
    if (modelsWithoutKey.length > 0) {
      console.log(`\n❌ 缺少 API Key 的模型 (${modelsWithoutKey.length} 个):`);
      modelsWithoutKey.forEach(id => console.log(`   - ${id}`));
    } else {
      console.log(`\n✅ 所有模型均已配置 API Key`);
    }
    console.log(`   管理员默认密码: admin888`);
    console.log(`   数据库文件: ${DB_FILE}\n`);
  });
});
