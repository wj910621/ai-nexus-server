/**
 * AI Nexus - 大模型聚合平台后端代理
 *
 * 统一代理多个 AI 模型提供商的 API，保护密钥安全。
 * 启动: npm start / npm run dev
 * 重启 (pm2): pm2 restart ai-nexus
 */

const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');
require('dotenv').config({ path: path.join(__dirname, '.env') });
const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 提供前端静态文件（支持多种目录结构：本地开发 / Railway 部署）
let staticDir = path.resolve(__dirname, '..');
if (!fs.existsSync(path.join(staticDir, 'index.html'))) {
  staticDir = __dirname; // 部署时 index.html 可能在同目录
}
console.log('静态文件目录:', staticDir);

// 首页
app.get('/', (req, res) => {
  res.sendFile(path.join(staticDir, 'index.html'));
});

// 其他静态资源
app.use(express.static(staticDir));

const PORT = process.env.PORT || 3001;

// ============================================================
// 模型到 API 配置的映射
// ============================================================
const MODEL_CONFIG = {
  gpt4o:        { provider: 'openai',   model: 'gpt-4o',             baseUrl: process.env.OPENAI_BASE_URL },
  gpt4omini:    { provider: 'openai',   model: 'gpt-4o-mini',        baseUrl: process.env.OPENAI_BASE_URL },
  deepseekv3:   { provider: 'openai',   model: 'deepseek-chat',      baseUrl: 'https://api.deepseek.com/v1' },
  deepseekr1:   { provider: 'openai',   model: 'deepseek-reasoner',  baseUrl: 'https://api.deepseek.com/v1' },
  gemini25pro:  { provider: 'gemini',   model: 'gemini-2.5-pro-exp-03-25' },
  gemini25flash:{ provider: 'gemini',   model: 'gemini-2.5-flash' },
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

  // === 七牛云合规 ===
  qiniu_claude37:     { provider: 'openai', model: 'claude-3-7-sonnet-20250219',  baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_claudeopus4:  { provider: 'openai', model: 'claude-opus-4-20250514',      baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_gpt4o:        { provider: 'openai', model: 'gpt-4o',                      baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_o3:           { provider: 'openai', model: 'o3',                          baseUrl: 'https://api.qnaiqc.com/v1' },
  qiniu_gemini25pro:  { provider: 'openai', model: 'gemini-2.5-pro',              baseUrl: 'https://api.qnaiqc.com/v1' },

  // === OpenRouter ===
  or_gpt4o:          { provider: 'openai', model: 'openai/gpt-4o',              baseUrl: 'https://openrouter.ai/api/v1' },
  or_claude_sonnet:  { provider: 'openai', model: 'anthropic/claude-3.5-sonnet', baseUrl: 'https://openrouter.ai/api/v1' },
  or_gemini25pro:    { provider: 'openai', model: 'google/gemini-2.5-pro-exp-03-25', baseUrl: 'https://openrouter.ai/api/v1' },
  or_llama3_70b:     { provider: 'openai', model: 'meta-llama/llama-3-70b-instruct', baseUrl: 'https://openrouter.ai/api/v1' },
  or_mistral_large:  { provider: 'openai', model: 'mistralai/mistral-large',    baseUrl: 'https://openrouter.ai/api/v1' },
  or_perplexity:     { provider: 'openai', model: 'perplexity/llama-3.1-sonar-huge-128k-online', baseUrl: 'https://openrouter.ai/api/v1' },
  or_codeqwen:       { provider: 'openai', model: 'qwen/qwen-2.5-coder-32b-instruct', baseUrl: 'https://openrouter.ai/api/v1' },
};

// 那些我们还没接入真实 API 但有模型的（Claude, Llama, Baichuan 等）
// 会返回友好的提示信息

// ============================================================
// API Key 管理
// ============================================================
function getApiKey(provider, modelId) {
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
    throw new Error(`API 调用失败 [${res.status}]: ${err}`);
  }

  const data = await res.json();
  return data.choices?.[0]?.message?.content || '(模型返回为空)';
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
// 模拟回复 (用于未配置 API Key 的模型)
// ============================================================
function getSimulatedReply(modelId, question) {
  const modelName = {
    gpt4o: 'GPT-4o', gpt4turbo: 'GPT-4 Turbo',
    claude35: 'Claude 3.5 Sonnet', claude3opus: 'Claude 3 Opus',
    gemini15pro: 'Gemini 1.5 Pro', gemini15flash: 'Gemini 1.5 Flash',
    deepseekv3: 'DeepSeek-V3', deepseekr1: 'DeepSeek-R1',
    qwen25: '通义千问 2.5', kimi: 'Kimi', glm4: 'GLM-4',
    yi: 'Yi-Large', hunyuan: '混元', baichuan4: 'Baichuan 4',
    minimax: 'MiniMax', doubao: '豆包', ernie40: '文心一言 4.0',
    spark4: '讯飞星火', step2: 'Step-2', sensechat: '日日新',
    llama31: 'Llama 3.1', mistral: 'Mistral Large',
    commandr: 'Command R+', phi3: 'Phi-3.5',
  };

  const name = modelName[modelId] || modelId;
  return `[${name} 模拟回复]\n\n关于「${question}」这个问题：\n\n⚠️ 该模型尚未配置 API Key，当前为模拟回复。\n\n如果需要真实 API 回复，请在 server/.env 文件中填入对应的 API Key 后重启服务。\n\n---\n模拟内容：这是一个很好的问题。从技术角度分析，这涉及到多个因素的综合考量。建议从以下几个方面入手：\n\n1. 明确需求和目标\n2. 评估可行方案\n3. 选择最优路径并持续迭代\n\n如需更深入的分析，请配置真实 API。`;
}

// ============================================================
// 统一聊天接口
// ============================================================
app.post('/api/chat', async (req, res) => {
  const { model: modelId, messages } = req.body;

  if (!modelId || !messages) {
    return res.status(400).json({ error: '缺少 model 或 messages 参数' });
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
    // 完全未知的模型 → 模拟回复
    const question = messages[messages.length - 1]?.content || '';
    return res.json({
      model: modelId,
      content: `[${modelId} 模拟回复]\n\n⚠️ 该模型暂未配置 API，当前为模拟回复。\n\n---\n模拟内容：这是一个很好的问题。从技术角度分析，这涉及到多个因素的综合考量。建议从以下几个方面入手：\n\n1. 明确需求和目标\n2. 评估可行方案\n3. 选择最优路径并持续迭代\n\n如需更深入的分析，请配置真实 API。`,
      simulated: true,
    });
  }

  const apiKey = getApiKey(config.provider, modelId);

  if (!apiKey) {
    // 未配置密钥 → 返回模拟回复
    const question = messages[messages.length - 1]?.content || '';
    return res.json({
      model: modelId,
      content: getSimulatedReply(modelId, question),
      simulated: true,
    });
  }

  try {
    let content;
    const startTime = Date.now();

    if (config.provider === 'openai') {
      content = await callOpenAICompatible(config, messages, apiKey);
    } else if (config.provider === 'gemini') {
      content = await callGemini(config, messages, apiKey);
    } else {
      return res.status(400).json({ error: `不支持的 provider: ${config.provider}` });
    }

    const latency = Date.now() - startTime;

    res.json({
      model: modelId,
      content,
      simulated: false,
      latency: `${latency}ms`,
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

app.get('/api/models-count', (req, res) => {
  res.json({ count: Object.keys(MODEL_CONFIG).length });
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
  const descMap = { '阿里百炼':'阿里云大模型，中文优化', '硅基流动':'硅基流动开源模型，按量付费', 'OpenRouter':'OpenRouter 聚合模型，全球200+模型' };
  return descMap[provider] || provider + '模型';
}

// ============================================================
// 阿里百炼模型动态拉取
// ============================================================
app.get('/api/bailian-models', async (req, res) => {
  const apiKey = process.env.DASHSCOPE_API_KEY;
  if (!apiKey) return res.json({ ok: false, models: [] });
  try {
    const r = await fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/models', {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await r.json();
    const models = (data.data || []).map(m => {
      const name = beautifyModelName(m.id, 'bailian');
      return {
        id: 'ali_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
        name,
        rawModel: m.id,
        avatar: genAvatarColor(name),
        desc: genModelDesc(name, '阿里百炼'),
        provider: '阿里百炼',
        context: '128K',
        inputPrice: (m.id || '').includes('免费') ? '免费' : '按量',
        outputPrice: (m.id || '').includes('免费') ? '免费' : '按量',
        tags: [],
        platform: 'bailian',
        free: (m.id || '').includes('免费'),
      };
    });
    res.json({ ok: true, count: models.length, models });
  } catch(e) {
    res.json({ ok: false, models: [] });
  }
});

// ============================================================
// 硅基流动模型动态拉取
// ============================================================
app.get('/api/siliconflow-models', async (req, res) => {
  const apiKey = process.env.SILICONFLOW_API_KEY;
  if (!apiKey) return res.json({ ok: false, models: [] });
  try {
    const r = await fetch('https://api.siliconflow.cn/v1/models', {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await r.json();
    const models = (data.data || []).map(m => {
      const name = beautifyModelName(m.id, 'siliconflow');
      return {
        id: 'sf_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
        name,
        rawModel: m.id,
        avatar: genAvatarColor(name),
        desc: genModelDesc(name, '硅基流动'),
        provider: '硅基流动',
        context: '64K',
        inputPrice: (m.id || '').includes('free') || (m.id || '').includes('免费') ? '免费' : '按量',
        outputPrice: (m.id || '').includes('free') || (m.id || '').includes('免费') ? '免费' : '按量',
        tags: [],
        platform: 'siliconflow',
        free: (m.id || '').includes('free') || (m.id || '').includes('免费'),
      };
    });
    res.json({ ok: true, count: models.length, models });
  } catch(e) {
    res.json({ ok: false, models: [] });
  }
});

// ============================================================
// OpenRouter 模型动态拉取
// ============================================================
app.get('/api/openrouter-models', async (req, res) => {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) return res.json({ ok: false, models: [] });
  try {
    const r = await fetch('https://openrouter.ai/api/v1/models', {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await r.json();
    const models = (data.data || []).map(m => {
      const name = beautifyModelName(m.id, 'openrouter');
      return {
        id: 'or_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
        name,
        rawModel: m.id,
        avatar: genAvatarColor(name),
        desc: genModelDesc(name, 'OpenRouter'),
        provider: 'OpenRouter',
        context: (m.context_length || '128K') + '',
        inputPrice: m.pricing ? (m.pricing.prompt || '?') : '?',
        outputPrice: m.pricing ? (m.pricing.completion || '?') : '?',
        tags: [],
        platform: 'openrouter',
        free: false,
      };
    });
    res.json({ ok: true, count: models.length, models });
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
// SQLite 数据库
// ============================================================
let db = null;
const DB_FILE = path.join(__dirname, 'data.db');
const SQL = require('sql.js');
async function initDB() {
  const initSql = fs.existsSync(DB_FILE) ? fs.readFileSync(DB_FILE) : null;
  const sql = await SQL();
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
  // 确保有 admin 用户
  const adminExists = db.exec("SELECT id FROM users WHERE username='admin'");
  if (!adminExists.length || !adminExists[0].values.length) {
    db.run("INSERT INTO users (username, email, password, credits, role) VALUES (?, ?, ?, ?, ?)",
      ['admin', 'admin@j3trisheng.com', btoaPwd('admin888'), 9999, 'admin']);
  }
  saveDB();
  console.log('数据库已就绪');
}

function btoaPwd(pwd) {
  return Buffer.from(pwd).toString('base64');
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
app.post('/api/auth/register', (req, res) => {
  const { username, email, password, refCode, deviceFp } = req.body;
  if (!username || !password) {
    return res.json({ ok: false, error: '请填写用户名和密码' });
  }
  const phone = (req.body.phone || '').trim();
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
    return res.json({ ok: false, error: '请填写正确的手机号' });
  }
  if (!/^[a-zA-Z0-9_\u4e00-\u9fa5]{2,20}$/.test(username)) {
    return res.json({ ok: false, error: '用户名格式不正确（2-20位字母/数字/中文/下划线）' });
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.json({ ok: false, error: '邮箱格式不正确' });
  }
  if (password.length < 6) {
    return res.json({ ok: false, error: '密码至少6位' });
  }
  // === 防多账号：同一IP永久最多注册2个账号 ===
  const clientIP = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
  const ipCount = db.exec("SELECT COUNT(*) FROM users WHERE register_ip=?", [clientIP]);
  const currentCount = (ipCount.length && ipCount[0].values.length) ? ipCount[0].values[0][0] : 0;
  if (currentCount >= 2) {
    return res.json({ ok: false, error: '本网络已注册过 2 个账号，已达到上限' });
  }
  try {
    const existing = db.exec("SELECT id FROM users WHERE username=? " + (email ? "OR email=?" : "") + " OR phone=?", 
      email ? [username, email, phone] : [username, phone]);
    if (existing.length && existing[0].values.length) {
      return res.json({ ok: false, error: '用户名、邮箱或手机号已被注册' });
    }
    const refCodeGen = 'J3' + username.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6) + Math.random().toString(36).slice(2, 5).toUpperCase();
    const userEmail = email || ('noemail_' + username + '@ai-nexus.local');
    let bonus = 10; // 注册赠送 10 积分（防薅：不够成本的量）
    let referrer = null;
    if (refCode) {
      const refUser = db.exec("SELECT username FROM users WHERE ref_code=? OR username=?", [refCode, refCode]);
      if (refUser.length && refUser[0].values.length) {
        bonus += 20;
        referrer = refUser[0].values[0][0];
        db.run("UPDATE users SET credits=credits+20 WHERE username=?", [referrer]);
        db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?, ?, ?)", [referrer, 20, '推荐奖励']);
      }
    }
    db.run("INSERT INTO users (username, email, password, credits, ref_code, referrer, register_ip, phone, device_fp) VALUES (?,?,?,?,?,?,?,?,?)",
      [username, userEmail, btoaPwd(password), bonus, refCodeGen, referrer, clientIP, phone||'', deviceFp||'']);
    db.run("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)", [username, bonus, '注册赠送']);
    saveDB();
    const token = Buffer.from(JSON.stringify({ username, role: 'user', ts: Date.now() })).toString('base64');
    res.json({ ok: true, token, user: { username, email, credits: bonus, refCode: refCodeGen }, bonus, referrerBonus: refCode ? 20 : 0 });
  } catch(e) {
    res.json({ ok: false, error: '注册失败: ' + e.message });
  }
});

app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.json({ ok: false, error: '请输入用户名和密码' });
  }
  try {
    const result = db.exec("SELECT username, email, password, credits, role, ref_code FROM users WHERE username=? OR email=?",
      [username, username]);
    if (!result.length || !result[0].values.length) {
      return res.json({ ok: false, error: '用户不存在' });
    }
    const user = result[0].values[0];
    if (user[2] !== btoaPwd(password)) {
      return res.json({ ok: false, error: '密码错误' });
    }
    const token = Buffer.from(JSON.stringify({ username: user[0], role: user[4], ts: Date.now() })).toString('base64');
    res.json({ ok: true, token, user: { username: user[0], email: user[1], credits: user[3], role: user[4], refCode: user[5] } });
  } catch(e) {
    res.json({ ok: false, error: '登录失败: ' + e.message });
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
    if (admin[1] !== btoaPwd(password)) {
      return res.json({ ok: false, error: '密码错误' });
    }
    const token = Buffer.from(JSON.stringify({ username: 'admin', role: 'admin', ts: Date.now() })).toString('base64');
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
    db.run("UPDATE users SET password=? WHERE username=? AND password=?", [btoaPwd(newPwd), 'admin', btoaPwd(oldPwd)]);
    saveDB();
    if (db.getRowsModified() === 0) {
      return res.json({ ok: false, error: '原密码错误' });
    }
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
// 启动服务
// ============================================================
initDB().then(() => {
  app.listen(PORT, () => {
    console.log(`\n⚡ AI Nexus 后端代理已启动`);
    console.log(`   本地访问: http://localhost:${PORT}`);
    console.log(`   API 状态: http://localhost:${PORT}/api/status`);

    // 检查各平台 Key 配置状态（按平台分组输出）
    const platforms = {};
    for (const [id, config] of Object.entries(MODEL_CONFIG)) {
      const platformKey = id.includes('_') ? id.split('_')[0] : config.provider;
      if (!platforms[platformKey]) {
        const envVar = getApiKey(config.provider, id);
        platforms[platformKey] = { configured: !!envVar, count: 0 };
      }
      platforms[platformKey].count++;
    }
    console.log(`\n📋 API Key 配置状态（${Object.keys(MODEL_CONFIG).length} 个模型）:`);
    for (const [name, info] of Object.entries(platforms).sort((a,b)=>a[0].localeCompare(b[0]))) {
      const icon = info.configured ? '✅' : '❌';
      console.log(`   ${icon} ${name.padEnd(14)} ${info.count} 个模型`);
    }
    console.log(`\n⚠️  未配置 Key 的模型将返回模拟回复`);
    console.log(`   管理员默认密码: admin888`);
    console.log(`   数据库文件: ${DB_FILE}\n`);
  });
});
