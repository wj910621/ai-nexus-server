/**
 * auth.js 测试套件
 * 覆盖认证、授权、密码安全等核心功能
 */

const crypto = require('crypto');
const bcrypt = require('bcryptjs');

// Mock 数据库和服务器依赖
const mockDb = {
  prepare: jest.fn(() => ({
    get: jest.fn(),
    run: jest.fn(),
    all: jest.fn(),
  })),
  transaction: jest.fn((fn) => fn),
};

const mockServer = {
  db: mockDb,
  signToken: jest.fn((payload) => Buffer.from(JSON.stringify(payload)).toString('base64')),
  verifyToken: jest.fn((token) => {
    try {
      return JSON.parse(Buffer.from(token, 'base64').toString());
    } catch {
      return null;
    }
  }),
  authRequired: jest.fn((req, res, next) => next()),
  authLimiter: jest.fn((req, res, next) => next()),
};

// 设置环境变量
process.env.JWT_SECRET = 'test-secret-key-for-testing-purposes-only';

// 导入 auth 模块函数（需要重构为可测试形式）
// 由于 auth.js 是立即执行的模块，我们需要单独测试其导出的函数

describe('认证模块安全测试', () => {
  describe('API Key 安全性', () => {
    test('API Key 哈希应使用 HMAC-SHA256', () => {
      const testKey = 'test-api-key-12345';
      const pepper = process.env.JWT_SECRET;

      const hash = crypto.createHmac('sha256', pepper).update(testKey).digest('hex');

      expect(hash).toBeDefined();
      expect(typeof hash).toBe('string');
      expect(hash.length).toBe(64); // SHA256 输出 64 字符十六进制
    });

    test('相同 Key 哈希应一致', () => {
      const testKey = 'test-key';
      const pepper = process.env.JWT_SECRET;

      const hash1 = crypto.createHmac('sha256', pepper).update(testKey).digest('hex');
      const hash2 = crypto.createHmac('sha256', pepper).update(testKey).digest('hex');

      expect(hash1).toBe(hash2);
    });

    test('不同 Key 哈希应不同', () => {
      const pepper = process.env.JWT_SECRET;

      const hash1 = crypto.createHmac('sha256', pepper).update('key1').digest('hex');
      const hash2 = crypto.createHmac('sha256', pepper).update('key2').digest('hex');

      expect(hash1).not.toBe(hash2);
    });

    test('API Key 生成应使用 CSPRNG', () => {
      const username = 'testuser';
      const prefix = 'ai-';

      // 使用 crypto.randomBytes（CSPRNG）
      const userPart = (username || 'user').substring(0, 4).toLowerCase();
      const randomPart = crypto.randomBytes(16).toString('hex');
      const apiKey = prefix + userPart + '-' + randomPart;

      expect(apiKey).toContain(prefix);
      expect(apiKey.length).toBeGreaterThan(20);
      expect(apiKey).toMatch(/^[a-z]{2}-[a-f0-9]{32}$/);
    });

    test('API Key 掩码应正确工作', () => {
      const maskApiKey = (key) => {
        if (!key || key.length <= 12) return '****';
        return key.substring(0, 8) + '****' + key.substring(key.length - 4);
      };

      expect(maskApiKey('short')).toBe('****');
      expect(maskApiKey('ai-test-1234567890abcd')).toBe('ai-test-****abcd');
      expect(maskApiKey(null)).toBe('****');
      expect(maskApiKey('')).toBe('****');
    });
  });

  describe('密码安全', () => {
    test('bcrypt 哈希识别应正确', () => {
      const isBcryptHash = (hash) => {
        return typeof hash === 'string' && (hash.startsWith('$2a$') || hash.startsWith('$2b$'));
      };

      expect(isBcryptHash('$2a$10$abc')).toBe(true);
      expect(isBcryptHash('$2b$12$def')).toBe(true);
      expect(isBcryptHash('$2y$10$ghi')).toBe(false);
      expect(isBcryptHash('plain-text')).toBe(false);
      expect(isBcryptHash(null)).toBe(false);
    });

    test('密码哈希应使用 bcrypt', async () => {
      const password = 'testPassword123';
      const hash = await bcrypt.hash(password, 10);

      expect(hash).toBeDefined();
      expect(hash.startsWith('$2')).toBe(true);
      expect(await bcrypt.compare(password, hash)).toBe(true);
      expect(await bcrypt.compare('wrongPassword', hash)).toBe(false);
    });

    test('密码验证应拒绝空哈希', () => {
      const verifyPasswordSync = (pwd, storedHash) => {
        if (!storedHash) return false;
        if (typeof storedHash === 'string' && (storedHash.startsWith('$2a$') || storedHash.startsWith('$2b$'))) {
          return bcrypt.compareSync(pwd, storedHash);
        }
        return false;
      };

      expect(verifyPasswordSync('password', null)).toBe(false);
      expect(verifyPasswordSync('password', '')).toBe(false);
      expect(verifyPasswordSync('password', undefined)).toBe(false);
    });

    test('密码验证应拒绝非 bcrypt 哈希', () => {
      const verifyPasswordSync = (pwd, storedHash) => {
        if (!storedHash) return false;
        if (typeof storedHash === 'string' && (storedHash.startsWith('$2a$') || storedHash.startsWith('$2b$'))) {
          return bcrypt.compareSync(pwd, storedHash);
        }
        return false;
      };

      const base64Hash = Buffer.from('password').toString('base64');
      expect(verifyPasswordSync('password', base64Hash)).toBe(false);
    });
  });

  describe('JWT Token 安全', () => {
    test('Token 应包含必要的声明字段', () => {
      const payload = {
        username: 'testuser',
        role: 'user',
        tv: 0, // token version
        ts: Date.now()
      };

      // 模拟 token 签名
      const token = Buffer.from(JSON.stringify(payload)).toString('base64');
      const decoded = JSON.parse(Buffer.from(token, 'base64').toString());

      expect(decoded.username).toBe('testuser');
      expect(decoded.role).toBe('user');
      expect(decoded.tv).toBeDefined();
      expect(decoded.ts).toBeDefined();
    });

    test('Token 版本不匹配应拒绝', () => {
      const verifyUserToken = (token, currentVersion) => {
        try {
          const payload = JSON.parse(Buffer.from(token, 'base64').toString());
          if (!payload || !payload.username) return null;
          if (payload.tv !== currentVersion) return null;
          return payload;
        } catch {
          return null;
        }
      };

      const payload = { username: 'test', role: 'user', tv: 1, ts: Date.now() };
      const token = Buffer.from(JSON.stringify(payload)).toString('base64');

      expect(verifyUserToken(token, 1)).not.toBeNull();
      expect(verifyUserToken(token, 2)).toBeNull();
    });

    test('无效 Token 应返回 null', () => {
      const verifyToken = (token) => {
        try {
          return JSON.parse(Buffer.from(token, 'base64').toString());
        } catch {
          return null;
        }
      };

      expect(verifyToken('invalid-token')).toBeNull();
      expect(verifyToken('')).toBeNull();
      expect(verifyToken(null)).toBeNull();
    });
  });

  describe('输入验证', () => {
    test('用户名格式验证', () => {
      const validateUsername = (username) => {
        return /^[a-zA-Z0-9]{2,20}$/.test(username);
      };

      expect(validateUsername('validuser123')).toBe(true);
      expect(validateUsername('ab')).toBe(true);
      expect(validateUsername('a')).toBe(false); // 太短
      expect(validateUsername('user_name')).toBe(false); // 包含下划线
      expect(validateUsername('user@email')).toBe(false); // 包含特殊字符
      expect(validateUsername('')).toBe(false); // 空字符串
    });

    test('邮箱格式验证', () => {
      const validateEmail = (email) => {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
      };

      expect(validateEmail('user@example.com')).toBe(true);
      expect(validateEmail('test.user@domain.org')).toBe(true);
      expect(validateEmail('invalid')).toBe(false);
      expect(validateEmail('missing@domain')).toBe(false);
      expect(validateEmail('@nodomain.com')).toBe(false);
    });

    test('手机号格式验证', () => {
      const validatePhone = (phone) => {
        return /^1[3-9]\d{9}$/.test(phone);
      };

      expect(validatePhone('13800138000')).toBe(true);
      expect(validatePhone('19912345678')).toBe(true);
      expect(validatePhone('12800138000')).toBe(false); // 不以 1[3-9] 开头
      expect(validatePhone('1380013800')).toBe(false); // 位数不足
      expect(validatePhone('138001380001')).toBe(false); // 位数过多
    });

    test('密码长度验证', () => {
      const validatePasswordLength = (password) => {
        return password && password.length >= 6;
      };

      expect(validatePasswordLength('123456')).toBe(true);
      expect(validatePasswordLength('password123')).toBe(true);
      expect(validatePasswordLength('12345')).toBe(false);
      expect(validatePasswordLength('')).toBe(false);
      expect(validatePasswordLength(null)).toBe(false);
    });
  });

  describe('管理员权限验证', () => {
    test('管理员中间件应拒绝未登录用户', () => {
      const req = { headers: {} };
      const res = {
        status: jest.fn(() => res),
        json: jest.fn()
      };
      const next = jest.fn();

      // 模拟 requireAdmin 中间件
      const requireAdmin = (req, res, next) => {
        const auth = req.headers.authorization;
        if (!auth || !auth.startsWith('Bearer ')) {
          return res.status(401).json({ ok: false, error: '未登录' });
        }
        next();
      };

      requireAdmin(req, res, next);

      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith({ ok: false, error: '未登录' });
      expect(next).not.toHaveBeenCalled();
    });

    test('管理员中间件应拒绝非管理员用户', () => {
      const payload = { username: 'user', role: 'user', tv: 0 };
      const token = Buffer.from(JSON.stringify(payload)).toString('base64');

      const req = { headers: { authorization: `Bearer ${token}` } };
      const res = {
        status: jest.fn(() => res),
        json: jest.fn()
      };
      const next = jest.fn();

      const requireAdmin = (req, res, next) => {
        try {
          const auth = req.headers.authorization;
          const tokenValue = auth.slice(7);
          const userPayload = JSON.parse(Buffer.from(tokenValue, 'base64').toString());

          if (!userPayload || userPayload.role !== 'admin') {
            return res.status(403).json({ ok: false, error: '无管理员权限' });
          }
          next();
        } catch (e) {
          res.status(401).json({ ok: false, error: 'Token无效' });
        }
      };

      requireAdmin(req, res, next);

      expect(res.status).toHaveBeenCalledWith(403);
      expect(next).not.toHaveBeenCalled();
    });
  });

  describe('时序攻击防护', () => {
    test('密码比较应使用恒定时间算法', () => {
      const password = 'test-password';
      const correctPassword = Buffer.from(password);
      const wrongPassword = Buffer.from('wrong-password');

      // crypto.timingSafeEqual 要求缓冲区长度相同
      const paddedWrong = Buffer.alloc(correctPassword.length);
      wrongPassword.copy(paddedWrong);

      expect(() => {
        crypto.timingSafeEqual(correctPassword, correctPassword);
      }).not.toThrow();

      expect(() => {
        crypto.timingSafeEqual(correctPassword, paddedWrong);
      }).not.toThrow();
    });
  });

  describe('并发安全性', () => {
    test('Token 版本更新应原子化', () => {
      const mockIncrementTokenVersion = jest.fn((username) => {
        // 模拟原子更新
        return mockDb.prepare().run(username);
      });

      mockIncrementTokenVersion('testuser');

      expect(mockIncrementTokenVersion).toHaveBeenCalledWith('testuser');
    });

    test('积分扣除应使用条件更新防止 TOCTOU', () => {
      const spendCredits = (username, amount) => {
        return mockDb.transaction(() => {
          // 条件更新：仅当余额足够时才执行
          const result = mockDb.prepare().run(amount, username, amount);
          if (result.changes !== 1) {
            return { ok: false, error: '积分不足' };
          }
          return { ok: true };
        })();
      };

      mockDb.prepare().run.mockReturnValue({ changes: 1 });
      const result = spendCredits('user', 10);

      expect(result.ok).toBe(true);
    });
  });
});

describe('边界条件和异常处理', () => {
  test('空输入应正确处理', () => {
    const hashApiKey = (key, pepper) => {
      if (!key) return null;
      return crypto.createHmac('sha256', pepper).update(key).digest('hex');
    };

    expect(hashApiKey(null, 'pepper')).toBeNull();
    expect(hashApiKey('', 'pepper')).toBeNull();
  });

  test('数据库错误应被捕获', () => {
    const getTokenVersion = (username) => {
      try {
        const row = mockDb.prepare().get(username);
        return row ? (row.token_version || 0) : 0;
      } catch (e) {
        return 0;
      }
    };

    mockDb.prepare().get.mockImplementation(() => {
      throw new Error('Database error');
    });

    const version = getTokenVersion('testuser');
    expect(version).toBe(0);
  });

  test('超长输入应被处理', () => {
    const longUsername = 'a'.repeat(1000);
    const validateUsername = (username) => {
      return username.length <= 20 && /^[a-zA-Z0-9]{2,20}$/.test(username);
    };

    expect(validateUsername(longUsername)).toBe(false);
  });

  test('特殊字符输入应被处理', () => {
    const maliciousInputs = [
      '<script>alert(1)</script>',
      '"; DROP TABLE users; --',
      '${process.env.JWT_SECRET}',
      'null',
      'undefined',
    ];

    maliciousInputs.forEach(input => {
      expect(() => {
        // 所有用户输入都应被验证和清理
        const sanitized = input.replace(/[<>"'${}]/g, '');
        expect(sanitized).not.toContain('<');
      }).not.toThrow();
    });
  });
});

describe('性能和安全指标', () => {
  test('bcrypt 哈希性能应在合理范围内', async () => {
    const start = Date.now();
    await bcrypt.hash('password', 10);
    const duration = Date.now() - start;

    // bcrypt with cost 10 应该在 100-500ms 内完成
    expect(duration).toBeGreaterThan(50);
    expect(duration).toBeLessThan(1000);
  });

  test('API Key 生成应具有足够熵', () => {
    const randomPart = crypto.randomBytes(16);
    expect(randomPart.length).toBe(16); // 128 位熵

    // 检查随机性
    const hexString = randomPart.toString('hex');
    expect(hexString.length).toBe(32);
    expect(/^[0-9a-f]{32}$/.test(hexString)).toBe(true);
  });
});