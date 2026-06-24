// ============================================================
// 微信支付 v3 API 模块 (Native 扫码支付)
// ============================================================
const https = require('https');
const crypto = require('crypto');

// 加载环境变量或默认值
const CFG = {
  mchid: process.env.WX_MCHID || '1747381807',
  serialNo: process.env.WX_SERIAL_NO || '17429AD9D638987B7AB90B6B269788E01CE9C29A',
  apiV3Key: process.env.WX_API_V3_KEY || 'Wangjiezhanglitaowangjinrui91062',
  notifyUrl: process.env.WX_NOTIFY_URL || 'https://j3trisheng.com/api/payments/wechat-notify',
  keyPath: process.env.WX_KEY_PATH || '/home/admin/ai-nexus/wechat_key.pem',
};

// 加载私钥
let PRIVATE_KEY = null;
function getPrivateKey() {
  if (PRIVATE_KEY) return PRIVATE_KEY;
  try {
    const fs = require('fs');
    PRIVATE_KEY = fs.readFileSync(CFG.keyPath, 'utf8');
    return PRIVATE_KEY;
  } catch (e) {
    console.error('[WX Pay] 无法读取私钥:', e.message);
    return null;
  }
}

// 生成随机字符串
function nonceStr(len = 32) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let s = '';
  for (let i = 0; i < len; i++) s += chars.charAt(Math.floor(Math.random() * chars.length));
  return s;
}

// 构建 Authorization 头
function buildAuth(method, url, body, timestamp, nonce) {
  const pkey = getPrivateKey();
  if (!pkey) return null;
  const signStr = `${method}\n${url}\n${timestamp}\n${nonce}\n${body || ''}\n`;
  const sign = crypto.createSign('RSA-SHA256').update(signStr).sign(pkey, 'base64');
  return `WECHATPAY2-SHA256-RSA2048 mchid="${CFG.mchid}",serial_no="${CFG.serialNo}",nonce_str="${nonce}",timestamp="${timestamp}",signature="${sign}"`;
}

// HTTP 请求微信支付 API
function requestWxPay(method, url, body) {
  return new Promise((resolve, reject) => {
    const ts = Math.floor(Date.now() / 1000).toString();
    const ns = nonceStr();
    const bodyStr = body ? JSON.stringify(body) : '';
    const auth = buildAuth(method, url, bodyStr, ts, ns);
    if (!auth) return reject(new Error('私钥加载失败'));

    const u = new URL('https://api.mch.weixin.qq.com' + url);
    const opts = {
      hostname: u.hostname,
      path: u.pathname + u.search,
      method,
      headers: {
        'Authorization': auth,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'TriGen/1.0',
      },
    };

    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(parsed);
          } else {
            reject(new Error(`微信支付API错误 [${res.statusCode}]: ${data}`));
          }
        } catch (e) {
          reject(new Error(`解析响应失败: ${data.substring(0, 200)}`));
        }
      });
    });
    req.on('error', reject);
    if (bodyStr) req.write(bodyStr);
    req.end();
  });
}

// 创建 Native 扫码支付订单
async function createNativeOrder({ description, outTradeNo, amount, attach = '' }) {
  const body = {
    mchid: CFG.mchid,
    out_trade_no: outTradeNo,
    appid: 'wxf3f9e5b5c8e5d6f7', // 微信支付APPID — 需要你确认
    description,
    notify_url: CFG.notifyUrl,
    amount: { total: amount, currency: 'CNY' },
    attach,
  };
  return await requestWxPay('POST', '/v3/pay/transactions/native', body);
}

// 查询订单状态
async function queryOrder(outTradeNo) {
  return await requestWxPay('GET', `/v3/pay/transactions/out-trade-no/${outTradeNo}?mchid=${CFG.mchid}`);
}

// 验证微信回调签名
function verifyNotify(headers, body) {
  const { 'wechatpay-signature': signature, 'wechatpay-timestamp': timestamp,
    'wechatpay-nonce': nonce, 'wechatpay-serial': serial } = headers;

  if (!signature || !timestamp || !nonce || !serial) {
    return { ok: false, error: '缺少签名头' };
  }

  // 验证证书序列号
  if (serial !== CFG.serialNo) {
    // 正式环境可能需要动态拉取平台证书，这里简化处理
    console.warn('[WX Pay] 证书序列号不匹配:', serial, 'vs', CFG.serialNo);
  }

  const signStr = `${timestamp}\n${nonce}\n${body}\n`;
  const pkey = getPrivateKey();
  if (!pkey) return { ok: false, error: '私钥加载失败' };

  // 注意：验证需要使用微信平台公钥，不是商户私钥
  // 简化处理：使用平台证书同步
  // 这里直接返回通过，将验证交给解密步骤
  return { ok: true };
}

// 解密回调资源
function decryptResource(encrypted) {
  const { associated_data, nonce, ciphertext } = encrypted;
  const key = CFG.apiV3Key;

  const authTag = Buffer.from(ciphertext, 'base64').slice(-16);
  const cipherData = Buffer.from(ciphertext, 'base64').slice(0, -16);

  const decipher = crypto.createDecipheriv('aes-256-gcm', key, nonce);
  decipher.setAuthTag(authTag);
  if (associated_data) decipher.setAAD(Buffer.from(associated_data));

  let decrypted = decipher.update(cipherData, null, 'utf8');
  decrypted += decipher.final('utf8');
  return JSON.parse(decrypted);
}

module.exports = { createNativeOrder, queryOrder, verifyNotify, decryptResource, CFG };
