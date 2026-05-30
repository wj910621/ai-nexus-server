/**
 * AI Nexus - 大模型聚合平台后端代理
 *
 * 统一代理多个 AI 模型提供商的 API，保护密钥安全。
 * 启动: npm start / npm run dev
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 提供前端静态文件（支持多种目录结构：本地开发 / Railway 部署）
const fs = require('fs');
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
  yi:           { provider: 'openai',   model: 'yi-lightning',       baseUrl: 'https://api.lingyiwanwu.com/v1' },

  // === 硅基流动 SiliconFlow ===
  sf_deepseek_v32:  { provider: 'openai', model: 'deepseek-ai/DeepSeek-V3.2',      baseUrl: 'https://api.siliconflow.cn/v1' },
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
  dmx_gpt52_pro:     { provider: 'openai', model: 'gpt-5.2-pro',            baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_gemini3:       { provider: 'openai', model: 'gemini-3',               baseUrl: 'https://www.dmxapi.cn/v1' },
  dmx_minimax_m27:   { provider: 'openai', model: 'MiniMax-M2.7',           baseUrl: 'https://www.dmxapi.cn/v1' },
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
  if (modelId.startsWith('yi'))       return process.env.YI_API_KEY;
  if (modelId.startsWith('hunyuan'))  return process.env.HUNYUAN_API_KEY;
  if (modelId.startsWith('sf_'))     return process.env.SILICONFLOW_API_KEY;
  if (modelId.startsWith('ali_'))    return process.env.DASHSCOPE_API_KEY;  // 百炼共用阿里云Key
  if (modelId.startsWith('dmx_'))    return process.env.DMXAPI_API_KEY;

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
// Google Gemini 请求
// ============================================================
async function callGemini(config, messages, apiKey) {
  // 动态加载 Google SDK
  const { GoogleGenerativeAI } = require('@google/generative-ai');
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: config.model });

  // 转换消息格式
  const history = [];
  let lastUserContent = '';

  for (const msg of messages) {
    if (msg.role === 'user') {
      if (history.length > 0 && history[history.length - 1].role === 'user') {
        history[history.length - 1].parts[0].text += '\n' + msg.content;
      } else {
        history.push({ role: 'user', parts: [{ text: msg.content }] });
      }
      lastUserContent = msg.content;
    } else if (msg.role === 'assistant') {
      history.push({ role: 'model', parts: [{ text: msg.content }] });
    }
  }

  // 最后一条是当前问题
  if (history.length > 0 && history[history.length - 1].role === 'user') {
    const currentMsg = history.pop();
    const chat = model.startChat({ history });
    const result = await chat.sendMessage(currentMsg.parts[0].text);
    return result.response.text();
  } else {
    const result = await model.generateContent(lastUserContent || 'Hello');
    return result.response.text();
  }
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

  const config = MODEL_CONFIG[modelId];
  if (!config) {
    return res.status(400).json({ error: `不支持的模型: ${modelId}` });
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
// 启动服务
// ============================================================
app.listen(PORT, () => {
  console.log(`\n⚡ AI Nexus 后端代理已启动`);
  console.log(`   本地访问: http://localhost:${PORT}`);
  console.log(`   API 状态: http://localhost:${PORT}/api/status\n`);

  // 检查已配置的密钥
  const configured = [];
  const unconfigured = [];
  for (const [id, config] of Object.entries(MODEL_CONFIG)) {
    const apiKey = getApiKey(config.provider, id);
    (apiKey ? configured : unconfigured).push(id);
  }

  console.log(`✅ 已配置密钥 (${configured.length}): ${configured.join(', ') || '无'}`);
  console.log(`⚠️  未配置密钥 (${unconfigured.length}): ${unconfigured.join(', ') || '无'}`);
  console.log(`   未配置的模型将返回模拟回复\n`);
});
