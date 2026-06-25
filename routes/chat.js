const { db, verifyToken, getApiKey, MODEL_CONFIG } = require('../server');

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
  sf_hunyuan_a13b:1, sf_qwen35_397b:1, sf_qwq_32b:1,
  dmx_minimax_m27_free:0, dmx_glm_5_turbo_free:0, dmx_qwen3_coder_plus_free:0,
  dmx_qwen3_coder_next_free:0, dmx_doubao_seed_code:0, dmx_mimo_v2_pro_free:0,
  dmx_code_free:0, dmx_codex_free:0, dmx_kat_coder_free:0,
  dmx_qwen36_plus_free:1, dmx_code_free_x:0, dmx_qwen3_max_free:1,
  dmx_minimax_m25_free:0,
  ark_dbs2_mini:0, ark_dbp15l:0, ark_dbs2_lite:0,
  ark_dsv4f:0, ark_dbs1_6:0, ark_dbs1_8:0, ark_dbs_code:0,
  ark_dsv32:0, ark_dsv4p:0, ark_dbs2_pro:0, ark_glm47:0,
  ark_dbp15p:0, ark_dbs_char:0,
  nx_gpt5:8, nx_gpt5mini:3, nx_gpt5chat:5, nx_gpt5nano:2, nx_gpt5all:8,
  nx_gpt51chat:6, nx_gpt51codex:8, nx_gpt51codexmax:10,
  nx_gpt52chat:8, nx_gpt52pro:8, nx_gpt53chat:8, nx_gpt53codex:12,
  nx_gpt54pro:12, nx_gpt54mini:5, nx_gpt54nano:3,
  nx_gpt55pro:15, nx_gpt55:15,
  nx_claude_opus:12, nx_claude_sonnet:6, nx_claude_haiku:5,
  nx_gemini_pro:6, nx_o3mini:5, nx_dalle3:8, nx_flux:5, nx_suno:8, nx_grok3:8,
  meshy_text:288, meshy_image:288,
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

const FREE_ALWAYS = ['dmx_qwen35_2b_free', 'dmx_qwen3_17b_free', 'dmx_spark_lite_free', 'ark_dbs2_mini', 'ark_dbp15l', 'sf_deepseek_v3_free', 'sf_glm47', 'sf_qwen3_8b'];

function getMembership(user) {
  if (!user) return { name: '免费用户', dailyFreeCalls: 30, discount: 0, price: 0, creditsPerMonth: 0, desc: '基础体验' };
  const tier = user.membership || 'free';
  const expires = user.membership_expires || '';
  if (tier !== 'free' && expires && new Date(expires) < new Date()) return { name: '免费用户', dailyFreeCalls: 30, discount: 0, price: 0, creditsPerMonth: 0, desc: '基础体验' };
  const MEMBERSHIP_TIERS = {
    free:  { name: '免费用户', dailyFreeCalls: 30, discount: 0, price: 0, creditsPerMonth: 0, desc: '基础体验' },
    silver:{ name: '月度会员', dailyFreeCalls: 999, discount: 0.2, price: 49, creditsPerMonth: 1000, desc: '高端模型8折' },
    gold:  { name: '季度会员', dailyFreeCalls: 999, discount: 0.3, price: 119, creditsPerMonth: 3500, desc: '高端模型7折+返利5%' },
    platinum:{name: '年度会员', dailyFreeCalls: 999, discount: 0.5, price: 369, creditsPerMonth: 15000, desc: '高端模型5折+返利10%+3D五折' },
  };
  return MEMBERSHIP_TIERS[tier] || MEMBERSHIP_TIERS.free;
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
    if (internalToken && internalToken === global.__INTERNAL_SERVICE_TOKEN) {
      username = 'admin';
      userCredits = 99999;
    }

    if (apiKey && apiKey.length > 10) {
      let isJwt = false;
      try {
        const payload = verifyToken(apiKey);
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
        const payload = verifyToken(authToken);
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
      const today = new Date().toISOString().slice(0, 10);
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

    if (username && creditCost > 0) {
      if (userCredits < creditCost) {
        return res.status(402).json({ error: { message: `积分不足（需要${creditCost}分，当前${userCredits}分）`, type: 'insufficient_credits' } });
      }
      db.prepare("UPDATE users SET credits=credits-? WHERE username=?").run(creditCost, username);
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
        model: modelId,
        content,
        simulated: false,
        latency: `${latency}ms`,
        cost: creditCost,
        credits_remaining: remainingCredits,
      });
    } catch (error) {
      console.error(`[${modelId}] 调用失败:`, error.message);
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
      res.status(502).json({
        model: modelId,
        content: `❌ ${userMsg}\n\n技术详情: ${errMsg}`,
        error: true,
      });
    }
  });
};
