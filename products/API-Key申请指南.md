# 🔑 API Key 申请指南

---

## 第一阶段接入

### 1️⃣ 百度文心一言（免费额度）

**平台**：百度千帆
**入口**：https://qianfan.baidu.com/
**成本**：注册送 100万 tokens（足够测试）

**操作步骤：**
1. 注册登录百度千帆
2. 点击右上角「控制台」
3. 左侧「应用接入」→「创建应用」
4. 填写应用名称（如 AI Nexus）
5. 勾选模型：ERNIE-4.5 / ERNIE-3.5
6. 创建后拿到：**API Key** 和 **Secret Key**
7. 需要在 server.js 添加文心配置

**服务器环境变量名**（需补充到 .env）：
```
WENXIN_API_KEY=你的APIKey
WENXIN_SECRET_KEY=你的SecretKey
```

---

### 2️⃣ 字节豆包（免费额度）

**平台**：火山引擎
**入口**：https://www.volcengine.com/product/doubao
**成本**：注册送 50万 tokens

**操作步骤：**
1. 登录火山引擎（字节旗下）
2. 搜索「豆包大模型」
3. 点击「立即使用」
4. 进入「模型服务」→「API Key 管理」
5. 创建 API Key
6. 获取 **AccessKey** 和 **SecretKey**

**服务器环境变量名**：
```
DOUBAO_API_KEY=你的Key
```

---

### 3️⃣ Groq（免费！超快！）

**平台**：Groq Cloud
**入口**：https://console.groq.com/
**成本**：**完全免费**（限制：30 req/min）

**可用的模型：**
| 模型 | 说明 |
|------|------|
| Llama 3 70B | Meta最新开源，通用能力强 |
| Llama 3 8B | 轻量快速 |
| Mixtral 8x7B | 开源MoE |
| Gemma 2 | Google开源 |

**操作步骤：**
1. 打开 https://console.groq.com/
2. 注册（支持 Google/GitHub 账号）
3. 登录后 → 左侧「API Keys」
4. 点击「Create API Key」
5. 复制 Key

**服务器环境变量名**：
```
GROQ_API_KEY=gsk_你的Key
```

**Groq 配置示例（server.js 添加）**：
```javascript
groq_llama3:  { provider: 'openai', model: 'llama3-70b-8192', baseUrl: 'https://api.groq.com/openai/v1' },
groq_mixtral: { provider: 'openai', model: 'mixtral-8x7b-32768', baseUrl: 'https://api.groq.com/openai/v1' },
```

---

## 第二阶段接入（可选，需要海外支付方式）

### 4️⃣ Google Gemini 2.5

**入口**：https://aistudio.google.com/apikey
**注意**：需要海外网络环境（或代理）
**成本**：免费额度 1500 req/天
**环境变量**：`GEMINI_API_KEY`

### 5️⃣ Together AI（开源模型）

**入口**：https://api.together.xyz/
**注册送 $1**，开源模型集合最全
**环境变量**：`TOGETHER_API_KEY`

### 6️⃣ Fireworks AI

**入口**：https://fireworks.ai/
**注册送 $1**，Llama/Mixtral/DeepSeek 等开源模型
**环境变量**：`FIREWORKS_API_KEY`

---

## 配置汇总

### 第一步：申请 Key
根据上面指引，申请需要的 API Key

### 第二步：配置到服务器

SSH 登录到阿里云服务器：
```bash
ssh root@120.79.17.184
```

编辑 .env 文件：
```bash
cd /opt/ai-nexus-server
nano .env
```

追加新 Key（格式示例）：
```bash
# 百度文心
WENXIN_API_KEY=xxx
WENXIN_SECRET_KEY=xxx
# 豆包
DOUBAO_API_KEY=xxx
# Groq
GROQ_API_KEY=gsk_xxx
# Gemini（如果有）
GEMINI_API_KEY=xxx
```

保存（Ctrl+X → Y → 回车），然后重启：
```bash
pm2 restart ai-nexus
```

### 第三步：服务器端添加模型路由

在 `server/server.js` 的 `MODEL_CONFIG` 中添加对应配置，类似：
```javascript
wenxin45:   { provider: 'wenxin',  model: 'ernie-4.5' },
doubao15:   { provider: 'openai',  model: 'doubao-pro-32k', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
groq_llama: { provider: 'openai',  model: 'llama3-70b-8192', baseUrl: 'https://api.groq.com/openai/v1' },
```

### 第四步：验证

访问网站测试新模型能否正常对话响应。

---

## 当前接入计划

| 阶段 | 模型 | 成本 | 操作 |
|------|------|------|------|
| 🟢 立即 | Groq (Llama 3) | 免费 | 注册即用 |
| 🟢 立即 | 文心一言 | 免费额度 | 申请 Key |
| 🟢 立即 | 字节豆包 | 免费额度 | 申请 Key |
| 🟡 本周 | Gemini 2.5 | 免费额度 | 需海外IP |
| 🟡 本周 | Together AI | $1赠金 | 开源模型集合 |
| 🔵 下月 | 其他按需接入 | 按量付费 | 看用户需求 |
