// ============================================================
// 微信支付 v3 API 模块 (Native 扫码支付)
// ============================================================
const https = require('https');
const crypto = require('crypto');

// 加载环境变量或默认值
// 安全：所有敏感配置必须从环境变量读取，不再硬编码默认值。
// 缺少必需环境变量时将拒绝相关操作，而非使用泄露的默认值。
const CFG = {
  mchid: process.env.WX_MCHID || '',
  serialNo: process.env.WX_SERIAL_NO || '',
  apiV3Key: process.env.WX_API_V3_KEY || '',
  notifyUrl: process.env.WX_NOTIFY_URL || '',
  keyPath: process.env.WX_KEY_PATH || '',
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
    appid: 'wxe5db01613c33e1b5',
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
// 安全要求：必须使用微信平台证书（公钥）验证签名，而非商户私钥。
// 未配置平台证书时拒绝所有回调，防止伪造回调导致虚假充值。
function verifyNotify(headers, body) {
  const { 'wechatpay-signature': signature, 'wechatpay-timestamp': timestamp,
    'wechatpay-nonce': nonce, 'wechatpay-serial': serial } = headers;

  if (!signature || !timestamp || !nonce || !serial) {
    return { ok: false, error: '缺少签名头' };
  }

  // 防重放：时间戳超过5分钟的回调拒绝
  const now = Math.floor(Date.now() / 1000);
  const cbTimestamp = parseInt(timestamp, 10);
  if (isNaN(cbTimestamp) || Math.abs(now - cbTimestamp) > 300) {
    console.error('[WX Pay] 回调时间戳过期或异常:', timestamp);
    return { ok: false, error: '回调时间戳过期' };
  }

  // 尝试加载微信平台证书进行签名验证
  const certPath = process.env.WX_PLATFORM_CERT_PATH;
  if (!certPath) {
    console.error('[WX Pay] 未配置 WX_PLATFORM_CERT_PATH，无法验证回调签名。请在环境变量中设置微信平台证书路径。');
    return { ok: false, error: '未配置平台证书，回调验证不可用' };
  }

  try {
    const fs = require('fs');
    const certPem = fs.readFileSync(certPath, 'utf8');
    const signStr = `${timestamp}\n${nonce}\n${body}\n`;

    const verify = crypto.createVerify('RSA-SHA256');
    verify.update(signStr);
    const ok = verify.verify(certPem, signature, 'base64');

    if (!ok) {
      console.error('[WX Pay] 回调签名验证失败');
      return { ok: false, error: '签名验证失败' };
    }

    return { ok: true };
  } catch (e) {
    console.error('[WX Pay] 平台证书加载或签名验证异常:', e.message);
    return { ok: false, error: '签名验证异常: ' + e.message };
  }
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
