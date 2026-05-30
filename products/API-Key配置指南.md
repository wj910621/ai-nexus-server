# 🔑 API Key 配置指南

---

## 当前状态

| API | 环境变量 | 状态 | 操作 |
|-----|----------|------|------|
| DeepSeek | `DEEPSEEK_API_KEY` | ✅ 已配 | 不用管 |
| 通义千问 | `DASHSCOPE_API_KEY` | ✅ 已配 | 不用管 |
| Kimi | `MOONSHOT_API_KEY` | ✅ 已配 | 不用管 |
| GLM | `ZHIPU_API_KEY` | ✅ 已配 | 不用管 |
| 混元 | `HUNYUAN_API_KEY` | ✅ 已配 | 不用管 |
| **七牛云** | **`OPENAI_API_KEY` + `OPENAI_BASE_URL`** | ❌ 缺失 | 需重新提取 |
| Gemini | `GEMINI_API_KEY` | ❌ 缺失 | 需申请 |
| Yi | `YI_API_KEY` | ❌ 缺失 | 暂缓 |

---

## 一、七牛云 API Key（优先级最高）

七牛云负责：**GPT-4o / GPT-4o-mini / Claude 系列**

之前密钥已重置，现在需要重新从七牛云后台获取。

### 操作步骤

**1** 打开 → https://portal.qiniu.com/

**2** 登录你的七牛云账号

**3** 左侧菜单 → **"密钥管理"**（或搜索 "AccessKey"）

**4** 点击 **"创建密钥"**（或查看已有的）

**5** 你会看到两个值：

| 字段 | 对应环境变量 |
|------|-------------|
| **AccessKey** | 不用管 |
| **SecretKey** | 就是 `OPENAI_API_KEY` |

### 获取 Base URL（OPENAI_BASE_URL）

七牛云作为 OpenAI 的网关，base URL 一般是：

```
https://api.qnaigc.com/v1
```

（如果这个不对，去七牛云控制台找 API 网关的接入地址）

### 配置到服务器

#### 方式A：直接 SSH 修改（推荐）

在 Git Bash 执行：

```bash
ssh root@120.79.17.184
```

输入密码登录后，执行：

```bash
cd /opt/ai-nexus-server
echo "OPENAI_API_KEY=你从七牛云获取的SecretKey" >> .env
echo "OPENAI_BASE_URL=https://api.qnaigc.com/v1" >> .env
pm2 restart ai-nexus
exit
```

#### 方式B：用编辑工具

同样的 SSH 登录后：

```bash
cd /opt/ai-nexus-server
nano .env
```

在文件末尾添加：
```
OPENAI_API_KEY=你从七牛云获取的SecretKey
OPENAI_BASE_URL=https://api.qnaigc.com/v1
```

`Ctrl+X` → `Y` → 回车保存，然后重启：

```bash
pm2 restart ai-nexus
```

---

## 二、Gemini API Key（次优先）

**申请地址：** https://aistudio.google.com/apikey

### 步骤
1. 打开链接，登录 Google 账号
2. 点击 **"Create API Key"**
3. 复制生成的 Key

### 配置到服务器

```bash
ssh root@120.79.17.184
```

输入密码登录，然后：

```bash
cd /opt/ai-nexus-server
echo "GEMINI_API_KEY=你的GeminiKey" >> .env
pm2 restart ai-nexus
exit
```

> ⚠️ Google Gemini 在国内可能访问不稳定，建议对 region 做判断：国内用户优先走七牛云/DeepSeek，海外用户可以走 Gemini。

---

## 三、Yi API Key（可暂缓）

**申请地址：** https://platform.lingyiwanwu.com/

注册后创建 API Key，后续如需再配置。

---

## 验证配置

配置完成后，在 Git Bash 测试任意一个模型是否正常工作：

```bash
curl http://120.79.17.184:3001/api/models
```

能看到模型列表里相应模型显示 `"configured":true` 就算成功了。
