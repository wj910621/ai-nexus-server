const crypto = require('crypto');
const { verifyNotify } = require('./wechat-pay');

const TEST_API_V3_KEY = 'test_api_v3_key_for_testing_12345678';
const TEST_SERIAL_NO = '17429AD9D638987B7AB90B6B269788E01CE9C29A';

function generateValidSignature(timestamp, nonce, body, apiKey) {
  const signStr = `${timestamp}\n${nonce}\n${body}\n`;
  return crypto.createHmac('sha256', apiKey)
    .update(signStr)
    .digest('base64');
}

async function runTests() {
  console.log('\n=== 微信支付回调签名验证测试 ===\n');
  
  const body = JSON.stringify({
    resource: {
      associated_data: '',
      nonce: 'abc123',
      ciphertext: 'test_ciphertext'
    }
  });
  
  const timestamp = '1699999999';
  const nonce = 'random_nonce_string';
  const validSignature = generateValidSignature(timestamp, nonce, body, TEST_API_V3_KEY);
  
  const originalApiV3Key = process.env.WX_API_V3_KEY;
  const originalSerialNo = process.env.WX_SERIAL_NO;
  
  process.env.WX_API_V3_KEY = TEST_API_V3_KEY;
  process.env.WX_SERIAL_NO = TEST_SERIAL_NO;
  
  const tests = [
    {
      name: '缺少签名头',
      headers: {
        'wechatpay-timestamp': timestamp,
        'wechatpay-nonce': nonce,
        'wechatpay-serial': TEST_SERIAL_NO
      },
      body,
      expectOk: false,
      expectError: '缺少签名头'
    },
    {
      name: '证书序列号不匹配',
      headers: {
        'wechatpay-signature': validSignature,
        'wechatpay-timestamp': timestamp,
        'wechatpay-nonce': nonce,
        'wechatpay-serial': 'WRONG_SERIAL_NUMBER'
      },
      body,
      expectOk: false,
      expectError: '证书序列号不匹配'
    },
    {
      name: '签名验证失败（伪造签名）',
      headers: {
        'wechatpay-signature': 'invalid_fake_signature_base64',
        'wechatpay-timestamp': timestamp,
        'wechatpay-nonce': nonce,
        'wechatpay-serial': TEST_SERIAL_NO
      },
      body,
      expectOk: false,
      expectError: '签名验证失败'
    },
    {
      name: '签名验证失败（错误的 body）',
      headers: {
        'wechatpay-signature': validSignature,
        'wechatpay-timestamp': timestamp,
        'wechatpay-nonce': nonce,
        'wechatpay-serial': TEST_SERIAL_NO
      },
      body: JSON.stringify({ different: 'body' }),
      expectOk: false,
      expectError: '签名验证失败'
    },
    {
      name: '签名验证失败（错误的 timestamp）',
      headers: {
        'wechatpay-signature': validSignature,
        'wechatpay-timestamp': 'wrong_timestamp',
        'wechatpay-nonce': nonce,
        'wechatpay-serial': TEST_SERIAL_NO
      },
      body,
      expectOk: false,
      expectError: '签名验证失败'
    },
    {
      name: '签名验证失败（错误的 nonce）',
      headers: {
        'wechatpay-signature': validSignature,
        'wechatpay-timestamp': timestamp,
        'wechatpay-nonce': 'wrong_nonce',
        'wechatpay-serial': TEST_SERIAL_NO
      },
      body,
      expectOk: false,
      expectError: '签名验证失败'
    },
    {
      name: '完整验证通过',
      headers: {
        'wechatpay-signature': validSignature,
        'wechatpay-timestamp': timestamp,
        'wechatpay-nonce': nonce,
        'wechatpay-serial': TEST_SERIAL_NO
      },
      body,
      expectOk: true,
      expectError: null
    }
  ];
  
  let passed = 0;
  let failed = 0;
  
  for (const test of tests) {
    console.log(`测试: ${test.name}`);
    const result = verifyNotify(test.headers, test.body);
    
    const okPass = result.ok === test.expectOk;
    const errorPass = test.expectError ? result.error === test.expectError : true;
    
    if (okPass && errorPass) {
      console.log(`  ✅ 通过 - ok: ${result.ok}, error: ${result.error || '无'}`);
      passed++;
    } else {
      console.log(`  ❌ 失败 - 期望 ok:${test.expectOk}, 实际 ok:${result.ok}, 期望 error:${test.expectError}, 实际 error:${result.error}`);
      failed++;
    }
    console.log('');
  }
  
  console.log(`\n测试结果: ${passed} 通过, ${failed} 失败`);
  
  if (originalApiV3Key !== undefined) process.env.WX_API_V3_KEY = originalApiV3Key;
  if (originalSerialNo !== undefined) process.env.WX_SERIAL_NO = originalSerialNo;
  
  process.exit(failed > 0 ? 1 : 0);
}

runTests();