const { db, verifyToken, getApiKey, MODEL_CONFIG } = require('./server');

// 安全：JWT 撤销校验。verifyToken 仅校验签名，不检查 token_version。
// 密码修改后 token_version 递增，旧 token 应立即失效。chat.js 是核心付费端点，
// 必须与 server.js authRequired / auth.js verifyUserToken 保持一致的撤销语义。
function verifyTokenWithRevocation(token) {
  const payload = verifyToken(token);
  if (payload && payload.username) {
    try {
      const row = db.prepare("SELECT token_version FROM users WHERE username=?").get(payload.username);
      const currentTv = row ? (row.token_version || 0) : 0;
      if (payload.tv !== currentTv) return null;  // token 已被撤销
    } catch (_) {
      // token_version 列可能尚未迁移，降级为仅校验签名（向后兼容）
    }
  }
  return payload;
}

// ============================================================
// 备用渠道配置（余额不足/故障时自动跳转）
// 按优先级排序，优先使用前面的，失败后自动尝试后面的
// ============================================================
const FALLBACK_CHAINS = {
  // ============================================================
  // 🟢 核心平台（余额用完不跳转，直接报错提醒充值）
  // 站长主要充值平台，稳定性优先
  // ============================================================
  
  // --- DeepSeek 官方（国产主力）---
  'deepseekv3': [],
  'deepseek-v3': [],
  'deepseekv4': [],
  'deepseek-v4': [],
  'deepseekr1': [],
  'deepseek-r1': [],

  // --- 阿里百炼（国产主力）---
  'qwen3': [],
  'qwen-3': [],
  'ali_qwen37_max': [],
  'ali_qwen36_plus': [],
  'ali_qwen36_flash': [],
  'ali_glm51': [],
  'ali_kimi_k26': [],
  'ali_deepseek_v4_pro': [],
  'ali_deepseek_v4_flash': [],

  // --- API Nexus（主渠道/最终兜底）---
  'nx_gpt5': [],
  'nx_gpt5mini': [],
  'nx_gpt5chat': [],
  'nx_gpt5nano': [],
  'nx_gpt5all': [],
  'nx_gpt51chat': [],
  'nx_gpt51codex': [],
  'nx_gpt51codexmax': [],
  'nx_gpt52chat': [],
  'nx_gpt52pro': [],
  'nx_gpt53chat': [],
  'nx_gpt53codex': [],
  'nx_gpt54pro': [],
  'nx_gpt54mini': [],
  'nx_gpt54nano': [],
  'nx_gpt55pro': [],
  'nx_gpt55': [],
  'nx_claude_opus': [],
  'nx_claude_sonnet': [],
  'nx_claude_haiku': [],
  'nx_gemini_pro': [],
  'nx_o3mini': [],
  'nx_dalle3': [],
  'nx_flux': [],
  'nx_suno': [],
  'nx_grok3': [],

  // --- 视频生成（Kling）---
  'kling_v1': [],
  'kling_v1_6': [],
  'kling_v2': [],

  // --- Suno 音乐 ---
  'suno_v3': [],
  'suno_v4': [],

  // --- Meshy 3D ---
  'meshy_text': [],
  'meshy_image': [],

  // --- 海外官方旗舰（用户明确选择时不跳转）---
  'gpt4o': [],
  'gpt-4o': [],
  'gpt4omini': [],
  'gpt-4o-mini': [],
  'claude4': [],
  'claude4opus': [],
  'claude-4-opus': [],
  'claude-4-sonnet': [],
  'gemini25pro': [],
  'gemini-2.5-pro': [],

  // ============================================================
  // 🔄 其他所有平台（余额不足 → 自动跳 API Nexus，用户无感）
  // ============================================================
  
  // --- 智谱 GLM ---
  'glm4plus': ['nx_gpt5mini'],
  'glm-4-plus': ['nx_gpt5mini'],
  'glm_51': ['nx_gpt5'],
  'glm_55': ['nx_gpt5'],
  'glm_5': ['nx_gpt5mini'],

  // --- 硅基流动 ---
  'sf_qwen35_397b': ['nx_gpt5'],
  'sf_qwq_32b': ['nx_gpt5mini'],
  'sf_glm5': ['nx_gpt5mini'],
  'sf_hunyuan_a13b': ['nx_gpt5mini'],
  'sf_deepseek_v3_free': ['nx_gpt5mini'],
  'sf_qwen3_8b': ['nx_gpt5mini'],
  'sf_qwen3_32b': ['nx_gpt5mini'],
  'sf_deepseek_v32': ['nx_gpt5mini'],

  // --- 月之暗面 Kimi ---
  'kimi2': ['nx_gpt5'],
  'kimi-k2': ['nx_gpt5'],
  'moonshot_v1': ['nx_gpt5'],

  // --- 腾讯混元 ---
  'hunyuan': ['nx_gpt5mini'],
  'hunyuan-turbos': ['nx_gpt5mini'],
  'hunyuan_a13b': ['nx_gpt5mini'],

  // --- 火山引擎 Ark ---
  'ark_dsv32': ['nx_gpt5mini'],
  'ark_dsv4f': ['nx_gpt5mini'],
  'ark_dsv4p': ['nx_gpt5'],
  'ark_dbs2_mini': ['nx_gpt5nano'],
  'ark_dbp15l': ['nx_gpt5mini'],
  'ark_dbs2_lite': ['nx_gpt5mini'],
  'ark_dbs1_6': ['nx_gpt5nano'],
  'ark_dbs1_8': ['nx_gpt5mini'],
  'ark_dbs_code': ['nx_gpt5mini'],
  'ark_dbs2_pro': ['nx_gpt5'],
  'ark_glm47': ['nx_gpt5mini'],
  'ark_dbp15p': ['nx_gpt5'],
  'ark_dbs_char': ['nx_gpt5mini'],
  'ark_doubao_pro': ['nx_gpt5mini'],
  'ark_doubao_lite': ['nx_gpt5nano'],

  // --- OpenRouter ---
  'or_gpt4o': ['nx_gpt5'],
  'or_claude_sonnet': ['nx_claude_sonnet'],
  'or_claude_opus': ['nx_claude_opus'],
  'or_gemini25pro': ['nx_gemini_pro'],
  'or_llama3_70b': ['nx_gpt5mini'],
  'or_mistral_large': ['nx_gpt5mini'],
  'or_perplexity': ['nx_gpt5mini'],
  'or_codeqwen': ['nx_gpt5mini'],

  // --- DMXAPI（全部免费/低价模型）---
  'dmx_qwen35_2b_free': ['nx_gpt5nano'],
  'dmx_qwen3_17b_free': ['nx_gpt5nano'],
  'dmx_spark_lite_free': ['nx_gpt5nano'],
  'dmx_qwen3_8b_free': ['nx_gpt5mini'],
  'dmx_qwen_flash_free': ['nx_gpt5nano'],
  'dmx_minimax_m25_free': ['nx_gpt5mini'],
  'dmx_minimax_m27_free': ['nx_gpt5'],
  'dmx_glm_47_free': ['nx_gpt5mini'],
  'dmx_glm_47_flash': ['nx_gpt5nano'],
  'dmx_glm_45_flash': ['nx_gpt5nano'],
  'dmx_glm_4_9b': ['nx_gpt5nano'],
  'dmx_hunyuan_lite': ['nx_gpt5nano'],
  'dmx_qwen35_plus_free': ['nx_gpt5mini'],
  'dmx_qwen3_5_plus_free': ['nx_gpt5mini'],
  'dmx_qwen35_35b_free': ['nx_gpt5'],
  'dmx_qwen25_coder_7b': ['nx_gpt5mini'],
  'dmx_doubao_seed_lite': ['nx_gpt5nano'],
  'dmx_mimo_v25_free': ['nx_gpt5mini'],
  'dmx_mimo_v2_pro_free': ['nx_gpt5mini'],
  'dmx_qwen3_coder_plus_free': ['nx_gpt5mini'],
  'dmx_qwen3_coder_next_free': ['nx_gpt5mini'],
  'dmx_doubao_seed_code': ['nx_gpt5mini'],
  'dmx_code_free': ['nx_gpt5mini'],
  'dmx_codex_free': ['nx_gpt5mini'],
  'dmx_kat_coder_free': ['nx_gpt5mini'],
  'dmx_qwen36_plus_free': ['nx_gpt5'],
  'dmx_code_free_x': ['nx_gpt5mini'],
  'dmx_qwen3_max_free': ['nx_gpt5'],
  'dmx_glm_5_free': ['nx_gpt5mini'],
  'dmx_glm_51_free': ['nx_gpt5'],
  'dmx_glm_5_turbo_free': ['nx_gpt5mini'],
  'dmx_kimi_k25_free': ['nx_gpt5'],
  'dmx_kimi_k26_free': ['nx_gpt5'],

  // --- 百川智能 ---
  'bc_baichuan4': ['nx_gpt5mini'],
  'bc_baichuan3': ['nx_gpt5nano'],

  // --- 七牛云 ---
  'qiniu_gpt4o': ['nx_gpt5'],
  'qiniu_o3': ['nx_gpt5'],
  'qiniu_claude37': ['nx_claude_sonnet'],
  'qiniu_claudeopus4': ['nx_claude_opus'],
  'qiniu_gemini25pro': ['nx_gemini_pro'],

  // --- 其他模型 ---
  'mistral-large2': ['nx_gpt5mini'],
  'grok3': ['nx_gpt5'],
  'spark4': ['nx_gpt5mini'],
  'llama4': ['nx_gpt5mini'],
  'doubao': ['nx_gpt5mini'],
  'doubao15': ['nx_gpt5mini'],
  'minimax1': ['nx_gpt5mini'],
  'gemini15flash': ['nx_gpt5mini'],
  'gemini15pro': ['nx_gpt5'],
  'gemini25flash': ['nx_gpt5mini'],
  'gpt4turbo': ['nx_gpt5'],
  'claude35': ['nx_claude_sonnet'],
  'claude3opus': ['nx_claude_opus'],
};

// 余额不足/额度耗尽的错误特征
const INSUFFICIENT_PATTERNS = [
  'insufficient', '余额不足', '额度不足', '余额为0', 'quota', 'exhausted',
  'balance', 'credit', '欠费', 'out of quota', 'rate limit', '429',
  'account_deactivated', 'billing', 'payment', '余额用尽', '额度已用完',
  'no balance', 'not enough', 'run out', 'expired', '已过期'
];

// 判断是否为余额不足/可降级的错误
function isInsufficientError(errMsg) {
  if (!errMsg) return false;
  const lower = errMsg.toLowerCase();
  // 401/403 是认证错误，不算余额不足，不应该降级
  if (lower.includes('[401]') || lower.includes('[403]') || lower.includes('401') && lower.includes('unauthorized')) return false;
  return INSUFFICIENT_PATTERNS.some(p => lower.includes(p.toLowerCase()));
}

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
// OpenAI 兼容格式请求
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
// Google Gemini 请求
// ============================================================
async function callGemini(config, messages, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${config.model}:generateContent?key=${apiKey}`;
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
// IP 速率限制
// ============================================================
const ipRateMap = new Map();
const IP_FREE_LIMIT = 20;
const IP_RATE_WINDOW = 60000;
const IP_RATE_MAX = 30;

function checkIpRate(ip, modelId) {
  const now = Date.now();
  const isHighCost = modelId.startsWith('nx_') || modelId.startsWith('or_') || modelId.startsWith('qiniu_') ||
    ['gpt4o','deepseekr1','claude4','claude4opus','gemini25pro','grok3'].includes(modelId);
  const isFree = modelId.startsWith('dmx_') || modelId.startsWith('ark_') ||
    ['sf_qwen3_8b','sf_deepseek_v3_free','sf_qwen3_32b','sf_glm47'].includes(modelId);
  if (isFree) return { blocked: false };
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
  if (record.count > IP_RATE_MAX) return { blocked: true, reason: `请求过频（${IP_RATE_MAX}次/分钟），请稍后重试` };
  if (isHighCost && record.dailyCount > IP_FREE_LIMIT) {
    return { blocked: true, reason: `高成本模型每日免费额度已用完（${IP_FREE_LIMIT}次），请注册并充值` };
  }
  return { blocked: false };
}

setInterval(() => {
  const now = Date.now();
  for (const [key, val] of ipRateMap) {
    if (now > val.dailyReset) ipRateMap.delete(key);
  }
}, 3600000);

// ============================================================
// 模型积分表
// ============================================================
const API_MODEL_COST = {
  dmx_qwen35_2b_free:0, dmx_qwen3_17b_free:0, dmx_spark_lite_free:0,
  sf_qwen3_8b:0, sf_deepseek_v3_free:0, dmx_qwen3_8b_free:0, dmx_qwen_flash_free:0,
  deepseekv3:1, glm4:1, kimi:1, sf_glm47:0, ali_qwen36_flash:1,
  dmx_minimax_m25_free:0, dmx_glm_47_free:0, dmx_glm_47_flash:0, dmx_glm_45_flash:0,
  dmx_glm_4_9b:0, dmx_hunyuan_lite:0, dmx_qwen35_plus_free:0,
  dmx_qwen3_5_plus_free:0, dmx_qwen35_35b_free:0, dmx_qwen25_coder_7b:0,
  dmx_doubao_seed_lite:0, dmx_mimo_v25_free:0, sf_qwen3_32b:0, or_codeqwen:1,
  glm4plus:1, minimax:1, spark4:1, ali_qwen36_plus:1, ali_deepseek_v4_flash:1,
  sf_hunyuan_a13b:0, sf_qwen35_397b:1, sf_qwq_32b:1,
  dmx_minimax_m27_free:0, dmx_glm_5_turbo_free:0, dmx_qwen3_coder_plus_free:0,
  dmx_qwen3_coder_next_free:0, dmx_doubao_seed_code:0, dmx_mimo_v2_pro_free:0,
  dmx_code_free:0, dmx_codex_free:0, dmx_kat_coder_free:0,
  dmx_qwen36_plus_free:1, dmx_code_free_x:0, dmx_qwen3_max_free:1,
  dmx_minimax_m25_free:0,
  ark_dbs2_mini:0, ark_dbp15l:0, ark_dbs2_lite:0,
  ark_dsv4f:0, ark_dbs1_6:0, ark_dbs1_8:0, ark_dbs_code:0,
  ark_dsv32:0, ark_dsv4p:0, ark_dbs2_pro:0, ark_glm47:0,
  ark_dbp15p:0, ark_dbs_char:0,
  nx_gpt5:8, nx_gpt5mini:3, nx_gpt5chat:5, nx_gpt5nano:3, nx_gpt5all:8,
  nx_gpt51chat:6, nx_gpt51codex:8, nx_gpt51codexmax:10,
  nx_gpt52chat:8, nx_gpt52pro:8, nx_gpt53chat:18, nx_gpt53codex:25,
  nx_gpt54pro:12, nx_gpt54mini:5, nx_gpt54nano:3,
  nx_gpt55pro:15, nx_gpt55:15,
  nx_claude_opus:12, nx_claude_sonnet:15, nx_claude_haiku:8,
  nx_gemini_pro:12, nx_o3mini:10, nx_dalle3:15, nx_flux:8, nx_suno:15, nx_grok3:15,
  meshy_text: 12, meshy_image: 12,
  ark_doubao_pro:0, ark_doubao_lite:0,
  bc_baichuan4:2, bc_baichuan3:1,
  qwen3:2, kimi2:2, minimax1:2, doubao:2, doubao15:2, gpt4omini:2, gemini15flash:2,
  ali_qwen37_max:2, ali_deepseek_v4_pro:2, ali_kimi_k26:2,
  sf_deepseek_v32:1, sf_glm5:2,
  deepseekr1:5, gpt4o:5, hunyuan:2, gemini15pro:5, gemini25flash:5,
  grok3:5, ali_glm51:3, 'mistral-large2':5,
  or_llama3_70b:5, or_mistral_large:5, or_perplexity:5, llama4:3,
  gpt4turbo:10, claude35:10, claude3opus:10, claude4:10,
  claude4opus:15, gemini25pro:10,
  or_gpt4o:10, or_claude_sonnet:10, or_gemini25pro:10,
  qiniu_claude37:10, qiniu_claudeopus4:10, qiniu_gpt4o:10, qiniu_o3:10, qiniu_gemini25pro:10,
  dmx_glm_5_free:0, dmx_glm_51_free:0, dmx_glm_5_turbo_free:0,
};

const FREE_ALWAYS = ['dmx_qwen35_2b_free', 'dmx_qwen3_17b_free', 'dmx_spark_lite_free', 'ark_dbs2_mini', 'ark_dbp15l', 'sf_deepseek_v3_free', 'sf_glm47', 'sf_qwen3_8b'];

function getMembership(user) {
  const FREE_FALLBACK = { name: '免费版', dailyCredits: 20, modelDiscount: 1, freeModelsPerDay: 10, dailyFreeCalls: 10, discount: 1, price: 0, creditsPerMonth: 0, desc: '基础体验' };
  if (!user) return FREE_FALLBACK;
  const tier = user.membership || 'free';
  const expires = user.membership_expires || '';
  const isLifetime = tier === 'lifetime_standard' || tier === 'lifetime_ultimate';
  if (tier !== 'free' && !isLifetime && expires && new Date(expires) < new Date()) return FREE_FALLBACK;
  const MEMBERSHIP_TIERS = {
    free: { name: '免费版', dailyCredits: 20, modelDiscount: 1, freeModelsPerDay: 10 },
    pro_monthly: { name: 'Pro会员', credits: 4000, modelDiscount: 1, freeModelsPerDay: 999 },
    pro_quarterly: { name: 'Pro季卡', credits: 13000, modelDiscount: 1, freeModelsPerDay: 999 },
    pro_yearly: { name: 'Pro年卡', credits: 52000, modelDiscount: 1, freeModelsPerDay: 999 },
    ultimate_monthly: { name: '旗舰会员', credits: 12000, modelDiscount: 0.8, freeModelsPerDay: 999 },
    ultimate_quarterly: { name: '旗舰季卡', credits: 40000, modelDiscount: 0.8, freeModelsPerDay: 999 },
    ultimate_yearly: { name: '旗舰年卡', credits: 160000, modelDiscount: 0.8, freeModelsPerDay: 999 },
    lifetime_standard: { name: '终身标准版', monthlyCredits: 4000, modelDiscount: 1, freeModelsPerDay: 999, purchaseDiscount: 0.8 },
    lifetime_ultimate: { name: '终身旗舰版', monthlyCredits: 12000, modelDiscount: 0.7, freeModelsPerDay: 999, purchaseDiscount: 0.7 },
  };
  let info = MEMBERSHIP_TIERS[tier];
  if (!info) {
    const t = String(tier).toLowerCase();
    if (t.includes('ultimate')) {
      info = MEMBERSHIP_TIERS.ultimate_monthly;
    } else if (t.includes('pro')) {
      info = MEMBERSHIP_TIERS.pro_monthly;
    } else if (t.includes('lifetime')) {
      info = MEMBERSHIP_TIERS.lifetime_standard;
    } else {
      info = MEMBERSHIP_TIERS.free;
    }
  }
  return Object.assign({ dailyFreeCalls: info.freeModelsPerDay, discount: info.modelDiscount, price: 0, creditsPerMonth: info.credits || info.monthlyCredits || 0, desc: info.name }, info);
}

module.exports = function(app) {
  app.post('/api/chat', async (req, res) => {
    const ip = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
    const apiKey = (req.headers.authorization || '').replace('Bearer ', '');
    const authToken = req.headers['x-auth-token'] || '';
    const { model: modelId, messages } = req.body;

    if (!modelId || !messages) {
      return res.status(400).json({ error: '缺少 model 或 messages 参数' });
    }

    let username = null;
    let userCredits = 0;
    const creditCost = API_MODEL_COST[modelId] !== undefined ? API_MODEL_COST[modelId] : 2;

    const internalToken = req.headers['x-internal-token'] || '';
    const clientIp = req.ip || req.connection?.remoteAddress || '';
    const allowedIps = ['127.0.0.1', '::1', '::ffff:127.0.0.1'];
    if (internalToken && internalToken === global.__INTERNAL_SERVICE_TOKEN && allowedIps.includes(clientIp)) {
      username = 'internal-service';
      userCredits = 99999;
    }

    if (apiKey && apiKey.length > 10) {
      let isJwt = false;
      try {
        const payload = verifyTokenWithRevocation(apiKey);
        if (payload && payload.username) {
          username = payload.username;
          const ur = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
          if (ur) userCredits = ur.credits || 0;
          isJwt = true;
        }
      } catch(e) { /* not JWT */ }
      if (!isJwt) {
        const keyResult = db.prepare(
          "SELECT a.username, a.active, u.credits FROM api_keys a JOIN users u ON a.username=u.username WHERE a.api_key=?"
        ).get(apiKey);
        if (!keyResult) {
          return res.status(401).json({ error: { message: '无效的 API Key', type: 'auth_error' } });
        }
        if (!keyResult.active) return res.status(403).json({ error: { message: 'API Key 已被禁用', type: 'auth_error' } });
        username = keyResult.username;
        userCredits = keyResult.credits || 0;
      }
    }

    if (!username && authToken && authToken.length > 10) {
      try {
        const payload = verifyTokenWithRevocation(authToken);
        if (payload && payload.username) {
          username = payload.username;
          const ur = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
          if (ur) userCredits = ur.credits || 0;
        }
      } catch(e) { /* token invalid */ }
    }

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
      const userResult = db.prepare("SELECT membership, membership_expires, daily_free_usage, daily_free_date FROM users WHERE username=?").get(username);
      let membershipInfo = { membership: 'free', expires: '', dailyFreeUsage: 0, dailyFreeDate: '' };
      if (userResult) {
        membershipInfo = { membership: userResult.membership, expires: userResult.membership_expires||'', dailyFreeUsage: userResult.daily_free_usage||0, dailyFreeDate: userResult.daily_free_date||'' };
      }
      const today = new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10);
      if (creditCost === 0 && !FREE_ALWAYS.includes(modelId)) {
        const dailyUsed = membershipInfo.dailyFreeDate === today ? membershipInfo.dailyFreeUsage : 0;
        const tier = getMembership(membershipInfo);
        if (modelId && dailyUsed >= tier.dailyFreeCalls) {
          return res.status(402).json({
            error: { message: `今日免费模型使用次数已达上限（${tier.dailyFreeCalls}次），开通会员可无限使用`, type: 'membership_required' }
          });
        }
        if (membershipInfo.dailyFreeDate === today) {
          db.prepare("UPDATE users SET daily_free_usage=daily_free_usage+1 WHERE username=?").run(username);
        } else {
          db.prepare("UPDATE users SET daily_free_usage=1, daily_free_date=? WHERE username=?").run(today, username);
        }
      }
    }

    const rateCheck = checkIpRate(ip, modelId);
    if (rateCheck.blocked) {
      const isPayingUser = username && userCredits >= (creditCost || 0);
      if (!isPayingUser || rateCheck.reason.includes('过频')) {
        console.log(`[RATE_LIMIT] ${ip} → ${modelId}: ${rateCheck.reason}`);
        return res.status(429).json({ error: { message: rateCheck.reason, type: 'rate_limit' } });
      }
      console.log(`[RATE_LIMIT] ${ip} → ${modelId}: 跳过每日限制（付费用户有积分）`);
    }

    if (username && creditCost > 0 && username !== 'internal-service') {
      const deductResult = db.prepare("UPDATE users SET credits=credits-? WHERE username=? AND credits>=?").run(creditCost, username, creditCost);
      if (deductResult.changes === 0) {
        return res.status(402).json({ error: { message: `积分不足（需要${creditCost}分，当前${userCredits}分）`, type: 'insufficient_credits' } });
      }
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, -creditCost, 'API: ' + modelId);
      if (apiKey) {
        db.prepare("UPDATE api_keys SET used=used+? WHERE api_key=?").run(creditCost, apiKey);
      }
    }

    let config = MODEL_CONFIG[modelId];
    if (!config) {
      const rawModel = req.body.rawModel || modelId;
      if (modelId.startsWith('or_')) {
        const key = process.env.OPENROUTER_API_KEY;
        if (key) {
          const m = rawModel.startsWith('or_') ? rawModel.replace(/^or_/, '') : rawModel;
          config = { provider: 'openai', model: m, baseUrl: 'https://openrouter.ai/api/v1' };
        }
      } else if (modelId.startsWith('sf_')) {
        const key = process.env.SILICONFLOW_API_KEY;
        if (key) {
          const m = rawModel.startsWith('sf_') ? rawModel.replace(/^sf_/, '') : rawModel;
          config = { provider: 'openai', model: m, baseUrl: 'https://api.siliconflow.cn/v1' };
        }
      } else if (modelId.startsWith('ali_')) {
        const key = process.env.DASHSCOPE_API_KEY;
        if (key) {
          const m = rawModel.startsWith('ali_') ? rawModel.replace(/^ali_/, '') : rawModel;
          config = { provider: 'openai', model: m, baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' };
        }
      }
    }

    if (!config) {
      console.log(`[UNKNOWN] 未找到模型配置: ${modelId}`);
      const question = messages[messages.length - 1]?.content || '';
      return res.status(400).json({
        model: modelId,
        content: `❌ 模型「${modelId}」未配置\n\n该模型不在当前支持的模型列表中。可能原因：\n1. 该模型为图片/语音/视频等非对话模型\n2. 模型 ID 已变更或下架\n3. 需要联系管理员添加配置\n\n支持列表刷新页面后在"模型选择"中查看。`,
        error: true,
      });
    }

    const providerApiKey = getApiKey(config.provider, modelId);
    let actualApiKey = providerApiKey;
    if (providerApiKey === 'qianfan') {
      actualApiKey = await getQianfanToken();
      if (!actualApiKey) {
        return res.status(500).json({ model: modelId, content: '❌ 百度千帆 Token 获取失败，请检查 AK/SK 配置。', error: true });
      }
    }

    if (!actualApiKey) {
      console.log(`[NO_KEY] ${modelId} 缺少 API Key`);
      return res.status(500).json({
        model: modelId,
        content: `❌ 模型「${modelId}」API Key 未配置\n\n该模型的后端 API 密钥未设置，暂时无法使用。请联系管理员在服务器环境变量中配置对应的 API Key。`,
        error: true,
      });
    }

    // 构建尝试列表：先当前模型，再依次尝试备用渠道
    const tryList = [modelId, ...(FALLBACK_CHAINS[modelId] || [])];
    const tried = new Set();
    let content = null;
    let finalModel = modelId;
    let lastError = null;
    let latency = 0;
    const startTime = Date.now();

    for (const tryModelId of tryList) {
      if (tried.has(tryModelId)) continue;
      tried.add(tryModelId);
      
      let tryConfig = MODEL_CONFIG[tryModelId];
      if (!tryConfig) {
        const rawModel = req.body.rawModel || tryModelId;
        if (tryModelId.startsWith('or_')) {
          const key = process.env.OPENROUTER_API_KEY;
          if (key) {
            const m = rawModel.startsWith('or_') ? rawModel.replace(/^or_/, '') : rawModel;
            tryConfig = { provider: 'openai', model: m, baseUrl: 'https://openrouter.ai/api/v1' };
          }
        } else if (tryModelId.startsWith('sf_')) {
          const key = process.env.SILICONFLOW_API_KEY;
          if (key) {
            const m = rawModel.startsWith('sf_') ? rawModel.replace(/^sf_/, '') : rawModel;
            tryConfig = { provider: 'openai', model: m, baseUrl: 'https://api.siliconflow.cn/v1' };
          }
        } else if (tryModelId.startsWith('ali_')) {
          const key = process.env.DASHSCOPE_API_KEY;
          if (key) {
            const m = rawModel.startsWith('ali_') ? rawModel.replace(/^ali_/, '') : rawModel;
            tryConfig = { provider: 'openai', model: m, baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' };
          }
        }
      }
      if (!tryConfig) continue;
      
      const tryApiKey = getApiKey(tryConfig.provider, tryModelId);
      let tryActualKey = tryApiKey;
      if (tryApiKey === 'qianfan') {
        tryActualKey = await getQianfanToken();
        if (!tryActualKey) continue;
      }
      if (!tryActualKey) continue;
      
      try {
        if (tryConfig.provider === 'openai' || tryConfig.provider === 'qianfan' || tryConfig.provider === 'nexus') {
          content = await callOpenAICompatible(tryConfig, messages, tryActualKey);
        } else if (tryConfig.provider === 'gemini') {
          content = await callGemini(tryConfig, messages, tryActualKey);
        } else {
          continue;
        }
        finalModel = tryModelId;
        lastError = null;
        break;
      } catch (err) {
        lastError = err;
        console.log(`[FALLBACK] ${tryModelId} 失败: ${err.message.substring(0,100)}，尝试下一个渠道`);
        // 只有余额不足/服务不可用/超时才降级，认证错误不降级
        if (!isInsufficientError(err.message) && 
            !err.message.includes('503') && !err.message.includes('524') && 
            !err.message.includes('timeout') && !err.message.includes('ETIMEDOUT') &&
            !err.message.includes('500') && !err.message.includes('502')) {
          break;
        }
      }
    }

    latency = Date.now() - startTime;

    if (!content) {
      const error = lastError || new Error('所有渠道均不可用');
      console.error(`[${modelId}] 所有渠道调用失败，最后错误:`, error.message);
      const errMsg = error.message || '未知错误';
      let userMsg = errMsg;
      if (errMsg.includes('503') || errMsg.includes('无可用渠道')) {
        userMsg = '该模型当前服务不可用，上游渠道暂不可用。请尝试其他模型。';
      } else if (errMsg.includes('524') || errMsg.includes('满载')) {
        userMsg = '上游服务器繁忙，请稍后重试或更换模型。';
      } else if (errMsg.includes('401') || errMsg.includes('User not found')) {
        userMsg = 'API 密钥无效或已过期，请联系管理员更新。';
      } else if (errMsg.includes('403') || errMsg.includes('disabled')) {
        userMsg = '该模型已被上游禁用，请尝试其他模型。';
      } else if (errMsg.includes('404') || errMsg.includes('NotFound')) {
        userMsg = '模型端点不存在，可能已下线。请尝试其他模型。';
      } else if (errMsg.includes('timeout') || errMsg.includes('ETIMEDOUT')) {
        userMsg = '请求超时，上游服务响应过慢。请重试或更换模型。';
      }
      if (username && creditCost > 0) {
        db.prepare("UPDATE users SET credits=credits+? WHERE username=?").run(creditCost, username);
        db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, creditCost, '退款: 所有渠道失败 ' + modelId);
      }
      // 安全：原始错误仅记录服务端日志，不向客户端泄露技术详情（端点/认证/堆栈）
      console.error(`[chat] 所有渠道失败 model=${modelId} user=${username}:`, errMsg);
      return res.status(502).json({
        model: modelId,
        content: `❌ ${userMsg}`,
        error: true,
      });
    }

    let remainingCredits = null;
    if (username) {
      const cr = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      if (cr) remainingCredits = cr.credits;
    }
    if (req.body.stream) {
      res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
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
      model: finalModel,
      content,
      simulated: false,
      latency: `${latency}ms`,
      cost: creditCost,
      credits_remaining: remainingCredits,
      fallback_used: finalModel !== modelId,
      original_model: modelId,
    });
  });
};
