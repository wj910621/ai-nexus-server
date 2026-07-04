const { MODEL_CONFIG, getApiKey } = require('../server');

// ============================================================
// 模型名称美化工具
// ============================================================
function beautifyModelName(rawId, platform) {
  let name = rawId;
  if (platform === 'bailian') {
    name = name.replace(/^vanchin\//, '')
               .replace(/^ZHIPU\//, '智谱 ')
               .replace(/^kimi\//, '')
               .replace(/^moonshotai\//, '月之暗面 ')
               .replace(/^deepseek-ai\//, '')
               .replace(/^[a-z0-9][a-z0-9_.-]*\//i, '');
    name = name.replace(/_/g, '-');
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
  if (platform === 'siliconflow') {
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
               .replace(/^[a-z0-9][a-z0-9_.-]*\//i, '');
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
  if (platform === 'openrouter') {
    const slashIdx = name.indexOf('/');
    if (slashIdx > 0) name = name.substring(slashIdx + 1);
    name = name.replace(/-/g, ' ')
               .replace(/\b\w/g, c => c.toUpperCase());
    name = name.replace(/\bGpt\b/i, 'GPT')
               .replace(/\bGlm\b/i, 'GLM')
               .replace(/\bLlm\b/i, 'LLM')
               .replace(/\bR1\b/i, 'R1')
               .replace(/\bV3\b/i, 'V3')
               .replace(/\bV4\b/i, 'V4')
               .replace(/^Qwen\b/i, '通义千问')
               .replace(/^Deepseek\b/i, 'DeepSeek')
               .replace(/^Gemma\b/i, 'Gemma')
               .replace(/^Mistral\b/i, 'Mistral')
               .replace(/^Claude\b/i, 'Claude')
               .replace(/^Llama\b/i, 'Llama')
               .replace(/^Gemini\b/i, 'Gemini');
  }
  if (name.includes('/') && name !== rawId) {
    name = name.split('/').pop();
  }
  return name;
}

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
function getDynamicCost(modelId) {
  const id = (modelId || '').toLowerCase();
  if (id.includes('免费') || id.includes('free') || id.includes('bge-') || id.includes('embed')) return 0;
  if (/[0-9]{1,2}b/i.test(id) && (id.includes('1.7b') || id.includes('2b') || id.includes('3b') || id.includes('4b') || id.includes('7b') || id.includes('8b'))) return 1;
  if (id.includes('flash') || id.includes('lite') || id.includes('turbo')) return 2;
  if (id.includes('plus') || id.includes('qwen3-') || id.includes('coder')) return 2;
  if (id.includes('max') || id.includes('pro') || id.includes('r1')) return 3;
  if (id.includes('opus') || id.includes('sonnet') || id.includes('gpt-4') || id.includes('claude')) return 10;
  if (id.includes('gemini') && id.includes('pro')) return 10;
  return 3;
}

const BAILIAN_CHAT_PREFIX = /^(qwen3\.\d|qwen3-\d|deepseek-v\d|glm-[4-9]|glm-1\d)/i;
function isBailianChatModel(modelId) {
  if (/image|wan|flux|stable|sd[-_]|asr|speech|tts|voice|audio|cosyvoice|gummy|paraformer|sambert|embed|bge[-_]|gte[-_]|video|deep[-_]research|rerank|realtime|MiniMax|kimi-L|abab|moonshot|step[-_]/i.test(modelId)) return false;
  return BAILIAN_CHAT_PREFIX.test(modelId);
}

const SILICONFLOW_CHAT_PREFIX = /^(Qwen\/Qwen3|Qwen\/QwQ|Qwen\/Qwen2\.5|deepseek-ai\/DeepSeek-V3|deepseek-ai\/DeepSeek-R1|Pro\/zai-org\/GLM|tencent\/Hunyuan|meta-llama\/Llama-4|meta-llama\/Llama-3\.[1-9]|mistralai\/Mistral|THUDM\/glm|01-ai\/Yi|internlm\/)/i;
const SF_NON_CHAT = /image|flux|stable|sd[-_]|video|cogvideo|embed|bge|asr|speech|tts|voice|audio/i;
function isSiliconFlowChatModel(modelId) {
  if (SF_NON_CHAT.test(modelId)) return false;
  return SILICONFLOW_CHAT_PREFIX.test(modelId);
}

const OPENROUTER_CHAT_PREFIX = /^(openai\/gpt-4|openai\/gpt-5|openai\/o[1-9]|anthropic\/claude-|google\/gemini-2|google\/gemini-1\.5|meta-llama\/llama-4|meta-llama\/llama-3\.[1-9]|mistralai\/mistral-large|mistralai\/mistral-small|qwen\/qwen-2\.5|qwen\/qwen3|deepseek\/deepseek-v|deepseek\/deepseek-r|perplexity\/|cohere\/command-r|amazon\/nova)/i;
const OR_NON_CHAT = /image|video|audio|tts|speech|embed|moderation/i;
function isOpenRouterChatModel(modelId) {
  if (OR_NON_CHAT.test(modelId)) return false;
  return OPENROUTER_CHAT_PREFIX.test(modelId);
}

module.exports = function(app) {
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
    res.json({ status: 'ok', uptime: process.uptime(), providers });
  });

  app.get('/api/models-list', (req, res) => {
    const allModels = Object.entries(MODEL_CONFIG).map(([id, cfg]) => ({
      id, name: cfg.model,
      provider: cfg.baseUrl ? new URL(cfg.baseUrl).hostname : cfg.provider,
      context: '128K', inputPrice: '?', outputPrice: '?', tags: [],
    }));
    res.json({ count: allModels.length, models: allModels });
  });

  app.get('/api/models', (req, res) => {
    const allModels = Object.entries(MODEL_CONFIG).map(([id, cfg]) => ({
      id, name: cfg.model,
      provider: cfg.baseUrl ? new URL(cfg.baseUrl).hostname : cfg.provider,
      context: '128K', inputPrice: '?', outputPrice: '?', tags: [],
    }));
    res.json({ count: allModels.length, models: allModels });
  });

  app.get('/api/models-count', async (req, res) => {
    let staticCount = Object.keys(MODEL_CONFIG).length;
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

  app.get('/api/bailian-models', async (req, res) => {
    const apiKey = process.env.DASHSCOPE_API_KEY;
    if (!apiKey) return res.json({ ok: false, models: [] });
    try {
      const r = await fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/models', {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });
      const data = await r.json();
      const models = (data.data || [])
        .filter(m => isBailianChatModel(m.id))
        .map(m => {
          const name = beautifyModelName(m.id, 'bailian');
          return {
            id: 'ali_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
            name, rawModel: m.id,
            avatar: genAvatarColor(name),
            desc: genModelDesc(name, '阿里云'),
            provider: '阿里云', context: '128K',
            inputPrice: (m.id || '').includes('免费') ? '免费' : '按量',
            outputPrice: (m.id || '').includes('免费') ? '免费' : '按量',
            tags: [], platform: 'bailian',
            free: (m.id || '').includes('免费'),
            cost: getDynamicCost(m.id),
          };
        });
      res.json({ ok: true, count: models.length, models, filtered: (data.data||[]).length - models.length });
    } catch(e) { res.json({ ok: false, models: [] }); }
  });

  app.get('/api/siliconflow-models', async (req, res) => {
    const apiKey = process.env.SILICONFLOW_API_KEY;
    if (!apiKey) return res.json({ ok: false, models: [] });
    try {
      const r = await fetch('https://api.siliconflow.cn/v1/models', {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });
      const data = await r.json();
      const models = (data.data || [])
        .filter(m => isSiliconFlowChatModel(m.id))
        .map(m => {
          const name = beautifyModelName(m.id, 'siliconflow');
          return {
            id: 'sf_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
            name, rawModel: m.id,
            avatar: genAvatarColor(name),
            desc: genModelDesc(name, '高性能'),
            provider: '高性能', context: '64K',
            inputPrice: (m.id || '').includes('free') || (m.id || '').includes('免费') ? '免费' : '按量',
            outputPrice: (m.id || '').includes('free') || (m.id || '').includes('免费') ? '免费' : '按量',
            tags: [], platform: 'siliconflow',
            free: (m.id || '').includes('free') || (m.id || '').includes('免费'),
            cost: getDynamicCost(m.id),
          };
        });
      res.json({ ok: true, count: models.length, models, filtered: (data.data||[]).length - models.length });
    } catch(e) { res.json({ ok: false, models: [] }); }
  });

  app.get('/api/openrouter-models', async (req, res) => {
    const apiKey = process.env.OPENROUTER_API_KEY;
    if (!apiKey) return res.json({ ok: false, models: [] });
    try {
      const r = await fetch('https://openrouter.ai/api/v1/models', {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });
      const data = await r.json();
      const models = (data.data || [])
        .filter(m => isOpenRouterChatModel(m.id))
        .map(m => {
          const name = beautifyModelName(m.id, 'openrouter');
          return {
            id: 'or_' + m.id.replace(/[^a-zA-Z0-9_-]/g, '_'),
            name, rawModel: m.id,
            avatar: genAvatarColor(name),
            desc: genModelDesc(name, '海外'),
            provider: '海外',
            context: (m.context_length || '128K') + '',
            inputPrice: m.pricing ? (m.pricing.prompt || '?') : '?',
            outputPrice: m.pricing ? (m.pricing.completion || '?') : '?',
            tags: [], platform: 'openrouter',
            free: false,
            cost: getDynamicCost(m.id),
          };
        });
      res.json({ ok: true, count: models.length, models, filtered: (data.data||[]).length - models.length });
    } catch(e) { res.json({ ok: false, models: [] }); }
  });
};
