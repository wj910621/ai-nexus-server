/**
 * Y·NEX - 积分定价系统（桌面端 Node.js 版本）
 *
 * 与主站 Python 版本保持同步
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function uuidv4() {
  return crypto.randomUUID ? crypto.randomUUID() :
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
}

const CREDIT_VALUE = 0.02475;

const MODEL_COSTS = {
  'deepseekv3': { input: 1, output: 4, provider: 'DeepSeek官方', tier: 'standard' },
  'deepseekr1': { input: 4, output: 16, provider: 'DeepSeek官方', tier: 'premium' },
  'qwen3': { input: 2, output: 8, provider: '阿里百炼', tier: 'standard' },
  'ali_qwen37_max': { input: 20, output: 80, provider: '阿里百炼', tier: 'premium' },
  'ali_qwen36_plus': { input: 4, output: 12, provider: '阿里百炼', tier: 'standard' },
  'ali_qwen36_flash': { input: 0.5, output: 2, provider: '阿里百炼', tier: 'free' },
  'ali_glm51': { input: 6, output: 28, provider: '阿里百炼', tier: 'premium' },
  'ali_kimi_k26': { input: 12, output: 12, provider: '阿里百炼', tier: 'premium' },
  'nx_gpt5': { input: 12.6, output: 50.4, provider: 'API Nexus', tier: 'flagship' },
  'nx_gpt5mini': { input: 0.756, output: 3.024, provider: 'API Nexus', tier: 'standard' },
  'nx_gpt5chat': { input: 5.04, output: 15.12, provider: 'API Nexus', tier: 'premium' },
  'nx_gpt5nano': { input: 0.504, output: 1.512, provider: 'API Nexus', tier: 'standard' },
  'nx_claude_opus': { input: 75.6, output: 378, provider: 'API Nexus', tier: 'flagship' },
  'nx_claude_sonnet': { input: 15.12, output: 75.6, provider: 'API Nexus', tier: 'premium' },
  'nx_claude_haiku': { input: 5.04, output: 25.2, provider: 'API Nexus', tier: 'standard' },
  'nx_gemini_pro': { input: 6.3, output: 25.2, provider: 'API Nexus', tier: 'premium' },
  'sf_qwen35_397b': { input: 2, output: 8, provider: '硅基流动', tier: 'standard' },
  'sf_qwq_32b': { input: 2, output: 6, provider: '硅基流动', tier: 'standard' },
  'sf_glm5': { input: 6, output: 28, provider: '硅基流动', tier: 'premium' },
  'sf_hunyuan_a13b': { input: 0.5, output: 0.5, provider: '硅基流动', tier: 'free' },
  'sf_qwen3_8b': { input: 0.5, output: 2, provider: '硅基流动', tier: 'free' },
  'sf_deepseek_v3_free': { input: 1, output: 4, provider: '硅基流动', tier: 'free' },
  'ark_dsv4p': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_dsv4f': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_dsv32': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_dbs2_pro': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_dbs2_lite': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_dbs2_mini': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_dbs_code': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'ark_glm47': { input: 0, output: 0, provider: '火山引擎', tier: 'free' },
  'glm4plus': { input: 0.5, output: 0.5, provider: '智谱官方', tier: 'free' },
  'hunyuan': { input: 1, output: 2, provider: '腾讯混元', tier: 'standard' },
  'kimi2': { input: 12, output: 12, provider: '月之暗面', tier: 'premium' },
  'gpt4o': { input: 18, output: 72, provider: 'OpenAI官方', tier: 'flagship' },
  'claude4': { input: 21.6, output: 108, provider: 'Anthropic官方', tier: 'flagship' },
  'gemini25pro': { input: 9, output: 36, provider: 'Google官方', tier: 'flagship' },
};

// 模型积分定价 - 与主站 user.js MODEL_COST 保持一致
const MODEL_CREDIT_PRICES = {
  // 免费模型
  'sf_qwen3_8b': 0, 'sf_deepseek_v3_free': 0, 'sf_hunyuan_a13b': 0,
  'ark_dsv4p': 0, 'ark_dsv4f': 0, 'ark_dsv32': 0,
  'ark_dbs2_pro': 0, 'ark_dbs2_lite': 0, 'ark_dbs2_mini': 0, 'ark_dbs_code': 0, 'ark_glm47': 0,
  // 入门级 1积分
  'glm4plus': 1, 'deepseekv3': 1, 'glm4': 1, 'kimi': 1, 'ali_qwen36_flash': 1,
  'minimax': 1, 'spark4': 1, 'ali_qwen36_plus': 1, 'ali_deepseek_v4_flash': 1,
  'sf_qwen35_397b': 1, 'sf_qwq_32b': 1, 'bc_baichuan3': 1,
  // 进阶 2积分
  'qwen3': 2, 'kimi2': 2, 'minimax1': 2, 'doubao': 2, 'doubao15': 2, 'gpt4omini': 2, 'gemini15flash': 2,
  'ali_qwen37_max': 2, 'ali_deepseek_v4_pro': 2, 'ali_kimi_k26': 2,
  'sf_glm5': 2, 'bc_baichuan4': 2, 'hunyuan': 2,
  // 高级 3积分
  'nx_gpt5mini': 3, 'nx_gpt5nano': 3, 'nx_gpt54nano': 3, 'llama4': 3, 'ali_glm51': 3,
  // 旗舰 5积分
  'deepseekr1': 5, 'gpt4o': 5, 'gemini15pro': 5, 'gemini25flash': 5,
  'grok3': 5, 'mistral-large2': 5,
  'nx_gpt5chat': 5, 'nx_gpt54mini': 5,
  // 高端 8积分
  'nx_gpt5': 8, 'nx_gpt5all': 8, 'nx_gpt51codex': 8, 'nx_gpt52chat': 8, 'nx_gpt52pro': 8,
  'nx_claude_haiku': 8, 'nx_flux': 8,
  // 尊享 10积分
  'nx_gpt51codexmax': 10, 'nx_o3mini': 10,
  'gpt4turbo': 10, 'claude35': 10, 'claude3opus': 10, 'claude4': 10, 'gemini25pro': 10,
  'or_gpt4o': 10, 'or_claude_sonnet': 10, 'or_gemini25pro': 10,
  'qiniu_claude37': 10, 'qiniu_claudeopus4': 10, 'qiniu_gpt4o': 10, 'qiniu_o3': 10, 'qiniu_gemini25pro': 10,
  // 顶级旗舰 12积分
  'nx_gpt54pro': 12, 'nx_gemini_pro': 12, 'meshy_text': 12, 'meshy_image': 12,
  // 至尊 15积分
  'nx_gpt55pro': 15, 'nx_gpt55': 15, 'nx_claude_sonnet': 15, 'nx_dalle3': 15, 'nx_suno': 15, 'nx_grok3': 15,
  'claude4opus': 15,
  // 顶级 18-25积分
  'nx_gpt53chat': 18,
  'nx_gpt53codex': 25,
};

const MEMBERSHIP_PLANS = {
  free: {
    name: '免费版', price: 0, period: 'forever',
    daily_credits: 20, max_concurrent: 1,
    features: ['每天20积分', '免费模型可用', '标准排队'],
    model_tiers: ['free'],
  },
  pro_monthly: {
    name: 'Pro会员', price: 99, price_credits: 4000, period: 'month',
    max_concurrent: 3, priority_queue: true,
    features: ['每月4000积分', '全部模型可用', '优先排队', '工作流无限使用', '多Agent协作', '知识库500条'],
    model_tiers: ['free', 'standard', 'premium', 'flagship'],
  },
  pro_quarterly: {
    name: 'Pro季卡', price: 269, price_credits: 13000, period: 'quarter',
    max_concurrent: 3, priority_queue: true,
    features: ['每季13000积分', '全部模型可用', '优先排队', '工作流无限使用', '多Agent协作', '知识库500条'],
    model_tiers: ['free', 'standard', 'premium', 'flagship'],
  },
  pro_yearly: {
    name: 'Pro年卡', price: 999, price_credits: 52000, period: 'year',
    max_concurrent: 5, priority_queue: true,
    features: ['每年52000积分', '全部模型可用', '极速排队', '工作流无限使用', '多Agent协作', '知识库1000条', '专属客服支持'],
    model_tiers: ['free', 'standard', 'premium', 'flagship'],
  },
  ultimate_monthly: {
    name: '旗舰会员', price: 299, price_credits: 12000, period: 'month',
    max_concurrent: 5, priority_queue: true, priority_level: 'high',
    features: ['每月12000积分', '全部模型可用', '极速排队', '工作流无限使用', '多Agent协作', '知识库无限', '专属客服支持', '新功能优先体验'],
    model_tiers: ['free', 'standard', 'premium', 'flagship', 'ultimate'],
  },
  ultimate_quarterly: {
    name: '旗舰季卡', price: 799, price_credits: 40000, period: 'quarter',
    max_concurrent: 5, priority_queue: true, priority_level: 'high',
    features: ['每季40000积分', '全部模型可用', '极速排队', '工作流无限使用', '多Agent协作', '知识库无限', '专属客服支持', '新功能优先体验'],
    model_tiers: ['free', 'standard', 'premium', 'flagship', 'ultimate'],
  },
  ultimate_yearly: {
    name: '旗舰年卡', price: 2999, price_credits: 160000, period: 'year',
    max_concurrent: 10, priority_queue: true, priority_level: 'ultra',
    features: ['每年160000积分', '全部模型可用', '至尊排队', '工作流无限使用', '多Agent协作', '知识库无限', '专属客服支持', '新功能优先体验'],
    model_tiers: ['free', 'standard', 'premium', 'flagship', 'ultimate'],
  },
  lifetime_standard: {
    name: '终身标准版', price: 899, monthly_credits: 4000, period: 'lifetime',
    max_concurrent: 3, priority_queue: true,
    features: ['永久每月4000积分', '全部模型可用', '优先排队', '工作流无限使用', '多Agent协作', '知识库500条', '加购积分享8折'],
    model_tiers: ['free', 'standard', 'premium', 'flagship'],
    limited: true, total_limit: 100, price_increase_rate: 0.15, normal_price: 1199,
    purchase_discount: 0.8,
  },
  lifetime_ultimate: {
    name: '终身旗舰版', price: 2599, monthly_credits: 12000, period: 'lifetime',
    max_concurrent: 10, priority_queue: true, priority_level: 'ultra',
    features: ['永久每月12000积分', '全部模型可用', '至尊排队', '工作流无限使用', '多Agent协作', '知识库无限', '专属客服支持', '未来新功能优先体验', '加购积分享7折'],
    model_tiers: ['free', 'standard', 'premium', 'flagship', 'ultimate'],
    limited: true, total_limit: 50, price_increase_rate: 0.2, normal_price: 3299,
    purchase_discount: 0.7,
  },
};

const CREDIT_PACKAGES = [
  { id: 'pack_100', name: '100积分', credits: 100, price: 9.9, bonus: 0 },
  { id: 'pack_500', name: '500积分', credits: 500, price: 45, bonus: 50 },
  { id: 'pack_1000', name: '1000积分', credits: 1000, price: 85, bonus: 150 },
  { id: 'pack_3000', name: '3000积分', credits: 3000, price: 240, bonus: 600 },
  { id: 'pack_10000', name: '10000积分', credits: 10000, price: 750, bonus: 3000 },
];

class CreditsSystem {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.dbPath = path.join(dataDir, 'credits.json');
    this.data = this._load();
  }

  _load() {
    try {
      if (fs.existsSync(this.dbPath)) {
        return JSON.parse(fs.readFileSync(this.dbPath, 'utf-8'));
      }
    } catch (e) {}
    return {
      users: {},
      transactions: [],
      lifetimeSales: [],
      config: { lifetimeSold: 0, lifetimeBatch: 1 },
    };
  }

  _save() {
    fs.mkdirSync(path.dirname(this.dbPath), { recursive: true });
    fs.writeFileSync(this.dbPath, JSON.stringify(this.data, null, 2), 'utf-8');
  }

  _today() {
    const d = new Date(Date.now() + 8 * 3600 * 1000);
    return d.toISOString().slice(0, 10);
  }

  _ensureUser(userId) {
    if (!this.data.users[userId]) {
      this.data.users[userId] = {
        userId,
        credits: 0,
        plan: 'free',
        planExpiresAt: null,
        dailyUsed: 0,
        dailyResetDate: this._today(),
        monthlyResetDate: this._thisMonth(),
        totalUsed: 0,
        createdAt: Date.now(),
      };
      this._save();
    }
    const u = this.data.users[userId];
    if (u.dailyResetDate !== this._today()) {
      u.dailyUsed = 0;
      u.dailyResetDate = this._today();
      this._save();
    }
    if (u.monthlyResetDate !== this._thisMonth()) {
      const plan = MEMBERSHIP_PLANS[u.plan];
      if (plan && plan.period === 'lifetime' && plan.monthly_credits) {
        u.credits = plan.monthly_credits;
        u.monthlyResetDate = this._thisMonth();
        this._save();
      }
    }
    return u;
  }

  _thisMonth() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
  }

  getUser(userId) {
    return this._ensureUser(userId);
  }

  getAvailableCredits(userId) {
    const u = this._ensureUser(userId);
    const plan = MEMBERSHIP_PLANS[u.plan] || MEMBERSHIP_PLANS.free;
    if (u.plan === 'free') {
      return Math.max(0, (plan.daily_credits || 10) - u.dailyUsed);
    }
    return u.credits;
  }

  isPlanActive(userId) {
    const u = this._ensureUser(userId);
    if (u.plan === 'free') return true;
    const plan = MEMBERSHIP_PLANS[u.plan];
    if (plan && plan.period === 'lifetime') return true;
    return u.planExpiresAt && u.planExpiresAt > Date.now();
  }

  downgradeIfExpired(userId) {
    const u = this._ensureUser(userId);
    if (u.plan === 'free') return false;
    const plan = MEMBERSHIP_PLANS[u.plan];
    if (!plan) return false;
    if (plan.period === 'lifetime') return false;
    if (u.planExpiresAt && u.planExpiresAt > Date.now()) return false;
    const oldPlan = u.plan;
    u.plan = 'free';
    u.planExpiresAt = null;
    this.data.transactions.push({
      id: uuidv4(), userId, type: 'downgrade', amount: 0,
      description: `套餐${plan.name || oldPlan}已过期，自动降级为免费版`,
      model: null, costPrice: null, createdAt: Date.now(),
    });
    this._save();
    return true;
  }

  canUseModel(userId, modelId) {
    this.downgradeIfExpired(userId);
    const u = this._ensureUser(userId);
    const plan = MEMBERSHIP_PLANS[u.plan] || MEMBERSHIP_PLANS.free;
    const model = MODEL_COSTS[modelId] || { tier: 'standard' };
    const tiers = plan.model_tiers || ['free', 'standard'];
    if (!tiers.includes(model.tier)) {
      return { ok: false, reason: '当前套餐不支持该模型，请升级套餐' };
    }
    return { ok: true };
  }

  deductCredits(userId, modelId, inputTokens = 0, outputTokens = 0, description = '') {
    this.downgradeIfExpired(userId);
    const u = this._ensureUser(userId);
    const cost = this.calculateCreditCost(modelId, inputTokens, outputTokens);

    if (cost === 0) {
      return { ok: true, cost: 0, reason: '免费模型' };
    }

    const check = this.canUseModel(userId, modelId);
    if (!check.ok) return { ok: false, cost: 0, reason: check.reason };

    const available = this.getAvailableCredits(userId);
    if (available < cost) {
      return { ok: false, cost, reason: `积分不足，需要${cost}积分，当前可用${available}积分` };
    }

    if (u.plan === 'free') {
      u.dailyUsed += cost;
    } else {
      u.credits -= cost;
    }
    u.totalUsed += cost;

    const costPrice = this.calculateCostPrice(modelId, inputTokens, outputTokens);
    this.data.transactions.push({
      id: uuidv4(), userId, type: 'consume', amount: cost,
      description: description || `使用 ${modelId}`,
      model: modelId, costPrice, createdAt: Date.now(),
    });

    this._save();
    return { ok: true, cost, reason: 'ok' };
  }

  addCredits(userId, amount, description = '充值', type = 'recharge') {
    if (amount > 1000000) throw new Error('充值金额超过上限');
    const u = this._ensureUser(userId);
    u.credits += amount;
    this.data.transactions.push({
      id: uuidv4(), userId, type, amount, description,
      model: null, costPrice: null, createdAt: Date.now(),
    });
    this._save();
    return true;
  }

  subscribePlan(userId, planId) {
    const plan = MEMBERSHIP_PLANS[planId];
    if (!plan) return { ok: false, reason: '套餐不存在' };

    const u = this._ensureUser(userId);
    const now = Date.now();

    if (u.plan === planId && this.isPlanActive(userId)) {
      if (plan.period === 'lifetime') {
        return { ok: true, plan: planId, credits: u.credits, renewed: true, message: '终身版已激活' };
      }
      const currentExpires = u.planExpiresAt && u.planExpiresAt > now ? u.planExpiresAt : now;
      if (plan.period === 'month') u.planExpiresAt = currentExpires + 30 * 24 * 3600 * 1000;
      else if (plan.period === 'quarter') u.planExpiresAt = currentExpires + 90 * 24 * 3600 * 1000;
      else if (plan.period === 'year') u.planExpiresAt = currentExpires + 365 * 24 * 3600 * 1000;
      this._save();
      return { ok: true, plan: planId, credits: u.credits, renewed: true };
    }

    if (plan.limited) {
      if (this.getLifetimeSoldCount(planId) >= plan.total_limit) {
        return { ok: false, reason: '终身版已售罄' };
      }
    }

    u.plan = planId;
    if (planId === 'pro_monthly') u.planExpiresAt = now + 30 * 24 * 3600 * 1000;
    else if (planId === 'pro_quarterly') u.planExpiresAt = now + 90 * 24 * 3600 * 1000;
    else if (planId === 'pro_yearly') u.planExpiresAt = now + 365 * 24 * 3600 * 1000;
    else if (planId === 'ultimate_monthly') u.planExpiresAt = now + 30 * 24 * 3600 * 1000;
    else if (planId === 'ultimate_quarterly') u.planExpiresAt = now + 90 * 24 * 3600 * 1000;
    else if (planId === 'ultimate_yearly') u.planExpiresAt = now + 365 * 24 * 3600 * 1000;
    else if (planId === 'lifetime_standard') u.planExpiresAt = now + 100 * 365 * 24 * 3600 * 1000;
    else if (planId === 'lifetime_ultimate') u.planExpiresAt = now + 100 * 365 * 24 * 3600 * 1000;
    else u.planExpiresAt = null;

    if (plan.price_credits) {
      u.credits += plan.price_credits;
      this.data.transactions.push({
        id: uuidv4(), userId, type: 'subscription', amount: plan.price_credits,
        description: `开通${plan.name}`, model: null, costPrice: null, createdAt: now,
      });
    }
    if (plan.monthly_credits && plan.period === 'lifetime') {
      u.credits += plan.monthly_credits;
      u.monthlyResetDate = this._thisMonth();
      this.data.transactions.push({
        id: uuidv4(), userId, type: 'subscription', amount: plan.monthly_credits,
        description: `${plan.name}本月积分`, model: null, costPrice: null, createdAt: now,
      });
    }

    if (plan.limited) {
      this.data.lifetimeSales.push({
        id: uuidv4(), userId, planId, price: this.getLifetimeCurrentPrice(planId),
        purchaseTime: now, batchNumber: this.getCurrentLifetimeBatch(planId),
      });
      this.data.config.lifetimeSold++;
      this._checkLifetimePriceIncrease(planId);
    }

    this._save();
    return { ok: true, plan: planId, credits: u.credits };
  }

  calculateCreditCost(modelId, inputTokens = 0, outputTokens = 0) {
    if (MODEL_CREDIT_PRICES[modelId] !== undefined) {
      return MODEL_CREDIT_PRICES[modelId];
    }
    const m = MODEL_COSTS[modelId];
    if (!m) return 2;
    const cost = (m.input * inputTokens + m.output * outputTokens) / 1e6;
    if (cost <= 0) return 0;
    const revenue = cost / 0.2;
    return Math.max(1, Math.ceil(revenue / CREDIT_VALUE));
  }

  calculateCostPrice(modelId, inputTokens = 0, outputTokens = 0) {
    const m = MODEL_COSTS[modelId];
    if (!m) return 0;
    return (m.input * inputTokens + m.output * outputTokens) / 1e6;
  }

  getProfitMargin(modelId) {
    const m = MODEL_COSTS[modelId];
    if (!m) return null;
    const price = MODEL_CREDIT_PRICES[modelId];
    if (price === undefined) return null;
    if (price === 0) return m.input === 0 && m.output === 0 ? 1 : null;
    const avgTokens = 4000;
    const cost = this.calculateCostPrice(modelId, avgTokens, avgTokens);
    const revenue = price * CREDIT_VALUE;
    if (revenue <= 0) return null;
    return (revenue - cost) / revenue;
  }

  getLifetimeSoldCount(planId) {
    if (planId) {
      return this.data.lifetimeSales.filter(s => s.planId === planId).length;
    }
    return this.data.lifetimeSales.length || this.data.config.lifetimeSold || 0;
  }
  getCurrentLifetimeBatch(planId) {
    if (!planId) return this.data.config.lifetimeBatch || 1;
    const plan = MEMBERSHIP_PLANS[planId];
    if (!plan) return 1;
    const sold = this.getLifetimeSoldCount(planId);
    const perBatch = 100;
    return Math.floor(sold / perBatch) + 1;
  }

  getLifetimeCurrentPrice(planId) {
    const plan = MEMBERSHIP_PLANS[planId];
    if (!plan) return 0;
    const base = plan.price;
    const batch = this.getCurrentLifetimeBatch(planId);
    const rate = plan.price_increase_rate || 0.1;
    return Math.round(base * Math.pow(1 + rate, batch - 1));
  }

  getLifetimeRemaining(planId) {
    if (planId) {
      const plan = MEMBERSHIP_PLANS[planId];
      if (!plan) return 0;
      return Math.max(0, plan.total_limit - this.getLifetimeSoldCount(planId));
    }
    let total = 0;
    for (const [pid, p] of Object.entries(MEMBERSHIP_PLANS)) {
      if (p.limited) total += Math.max(0, p.total_limit - this.getLifetimeSoldCount(pid));
    }
    return total;
  }

  _checkLifetimePriceIncrease(planId) {
    if (planId) {
      return false;
    }
    const sold = this.getLifetimeSoldCount();
    const batch = this.getCurrentLifetimeBatch();
    const perBatch = 100;
    const newBatch = Math.floor(sold / perBatch) + 1;
    if (newBatch > batch) {
      this.data.config.lifetimeBatch = newBatch;
      return true;
    }
    return false;
  }

  getAllPlans() {
    const result = {};
    for (const [pid, p] of Object.entries(MEMBERSHIP_PLANS)) {
      result[pid] = { ...p };
      if (p.limited) {
        result[pid].currentPrice = this.getLifetimeCurrentPrice(pid);
        result[pid].soldCount = this.getLifetimeSoldCount(pid);
        result[pid].remaining = this.getLifetimeRemaining(pid);
        result[pid].batch = this.getCurrentLifetimeBatch(pid);
      }
    }
    return result;
  }

  getCreditPackages(userId) {
    const packages = CREDIT_PACKAGES.map(p => ({ ...p }));
    if (userId) {
      const u = this._ensureUser(userId);
      const plan = MEMBERSHIP_PLANS[u.plan];
      if (plan && plan.purchase_discount && plan.purchase_discount < 1) {
        for (const pkg of packages) {
          pkg.originalPrice = pkg.price;
          pkg.price = Math.round(pkg.price * plan.purchase_discount * 100) / 100;
        }
      }
    }
    return packages;
  }

  getTransactions(userId, limit = 50, offset = 0) {
    return this.data.transactions
      .filter(t => t.userId === userId)
      .sort((a, b) => b.createdAt - a.createdAt)
      .slice(offset, offset + limit);
  }

  getUsageStats(userId, days = 30) {
    const since = Date.now() - days * 24 * 3600 * 1000;
    const txs = this.data.transactions.filter(t =>
      t.userId === userId && t.type === 'consume' && t.createdAt > since
    );
    const byModel = {};
    let totalCredits = 0, totalCost = 0;
    for (const tx of txs) {
      totalCredits += tx.amount;
      totalCost += tx.costPrice || 0;
      if (!byModel[tx.model]) byModel[tx.model] = { calls: 0, credits: 0, cost: 0 };
      byModel[tx.model].calls++;
      byModel[tx.model].credits += tx.amount;
      byModel[tx.model].cost += tx.costPrice || 0;
    }
    return {
      days, totalCalls: txs.length, totalCreditsUsed: totalCredits,
      totalCost, totalRevenue: totalCredits * CREDIT_VALUE,
      totalProfit: totalCredits * CREDIT_VALUE - totalCost,
      profitMargin: totalCredits > 0 ? (totalCredits * CREDIT_VALUE - totalCost) / (totalCredits * CREDIT_VALUE) : 0,
      byModel,
    };
  }

  async syncFromCloud(username, cloudData) {
    if (!username || !cloudData) return false;
    const u = this._ensureUser(username);
    u.credits = cloudData.credits !== undefined ? cloudData.credits : u.credits;
    u.plan = cloudData.plan || cloudData.membership || u.plan;
    u.planExpiresAt = cloudData.planExpiresAt || cloudData.membershipExpires || u.planExpiresAt;
    this._save();
    return true;
  }

  getUserSummary(userId) {
    const u = this._ensureUser(userId);
    return {
      credits: u.credits,
      plan: u.plan,
      planExpiresAt: u.planExpiresAt,
    };
  }

  getAdminStats() {
    const users = Object.values(this.data.users);
    const txs = this.data.transactions;
    const consumed = txs.filter(t => t.type === 'consume').reduce((s, t) => s + t.amount, 0);
    const recharged = txs.filter(t => t.type === 'recharge').reduce((s, t) => s + t.amount, 0);
    const totalCost = txs.filter(t => t.type === 'consume').reduce((s, t) => s + (t.costPrice || 0), 0);
    const planDist = {};
    for (const u of users) planDist[u.plan] = (planDist[u.plan] || 0) + 1;
    return {
      totalUsers: users.length,
      totalCreditsInCirculation: users.reduce((s, u) => s + u.credits, 0),
      totalCreditsConsumed: consumed,
      totalCreditsRecharged: recharged,
      totalCost,
      totalRevenue: consumed * CREDIT_VALUE,
      totalProfit: consumed * CREDIT_VALUE - totalCost,
      profitMargin: consumed > 0 ? (consumed * CREDIT_VALUE - totalCost) / (consumed * CREDIT_VALUE) : 0,
      planDistribution: planDist,
    };
  }
}

module.exports = {
  CreditsSystem,
  MODEL_COSTS,
  MODEL_CREDIT_PRICES,
  MEMBERSHIP_PLANS,
  CREDIT_PACKAGES,
  CREDIT_VALUE,
};
