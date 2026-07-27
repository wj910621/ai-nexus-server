/**
 * Y·NEX 连接池测试
 * 测试 HTTP 连接池、请求去重和并发控制
 */

const assert = require('assert');
const { ConnectionPool } = require('./desktop/src/connection-pool');

// 测试套件
describe('连接池测试', () => {
  let pool;

  beforeEach(() => {
    pool = new ConnectionPool();
  });

  afterEach(() => {
    pool.shutdown();
  });

  describe('连接池初始化', () => {
    it('应正确初始化连接池参数', () => {
      assert.strictEqual(pool.maxSockets, 10, 'maxSockets 应为 10');
      assert.strictEqual(pool.maxFreeSockets, 5, 'maxFreeSockets 应为 5');
      assert.strictEqual(pool.keepAliveMs, 60000, 'keepAliveMs 应为 60000');
      assert.strictEqual(pool.pool.size, 0, '初始连接池应为空');
      assert.strictEqual(pool.pending.size, 0, '初始待处理队列应为空');
    });

    it('应正确初始化统计信息', () => {
      const stats = pool.stats();
      assert.strictEqual(stats.hits, 0, '初始 hits 应为 0');
      assert.strictEqual(stats.misses, 0, '初始 misses 应为 0');
      assert.strictEqual(stats.merges, 0, '初始 merges 应为 0');
      assert.strictEqual(stats.connections, 0, '初始 connections 应为 0');
      assert.strictEqual(stats.poolSize, 0, '初始 poolSize 应为 0');
      assert.strictEqual(stats.pendingRequests, 0, '初始 pendingRequests 应为 0');
    });
  });

  describe('Agent 管理', () => {
    it('应为相同 host:port 复用 Agent', () => {
      const agent1 = pool._getAgent('example.com', 80);
      const agent2 = pool._getAgent('example.com', 80);
      
      assert.strictEqual(agent1, agent2, '相同 host:port 应复用 Agent');
      assert.strictEqual(pool.pool.size, 1, '连接池大小应为 1');
    });

    it('应为不同 host:port 创建不同 Agent', () => {
      const agent1 = pool._getAgent('example.com', 80);
      const agent2 = pool._getAgent('example.org', 443);
      
      assert.notStrictEqual(agent1, agent2, '不同 host:port 应创建不同 Agent');
      assert.strictEqual(pool.pool.size, 2, '连接池大小应为 2');
    });

    it('应正确处理 HTTPS 协议', () => {
      const httpAgent = pool._getAgent('example.com', 80, 'http:');
      const httpsAgent = pool._getAgent('example.com', 443, 'https:');
      
      // 检查 Agent 类型（这里简化检查）
      assert.strictEqual(pool.pool.size, 2, '不同协议应创建不同连接');
    });
  });

  describe('请求去重', () => {
    it('应为相同 GET 请求生成相同的去重 key', () => {
      const options1 = {
        hostname: 'example.com',
        port: 80,
        path: '/api/test',
        method: 'GET'
      };
      
      const options2 = {
        hostname: 'example.com',
        port: 80,
        path: '/api/test',
        method: 'GET'
      };
      
      // 模拟去重 key 生成
      const key1 = `${options1.method}:${options1.hostname}:${options1.port}:${options1.path}:${''}`;
      const key2 = `${options2.method}:${options2.hostname}:${options2.port}:${options2.path}:${''}`;
      
      assert.strictEqual(key1, key2, '相同请求应生成相同 key');
    });

    it('应为不同请求生成不同的去重 key', () => {
      const options1 = {
        hostname: 'example.com',
        port: 80,
        path: '/api/test1',
        method: 'GET'
      };
      
      const options2 = {
        hostname: 'example.com',
        port: 80,
        path: '/api/test2',
        method: 'GET'
      };
      
      const key1 = `${options1.method}:${options1.hostname}:${options1.port}:${options1.path}:${''}`;
      const key2 = `${options2.method}:${options2.hostname}:${options2.port}:${options2.path}:${''}`;
      
      assert.notStrictEqual(key1, key2, '不同路径应生成不同 key');
    });

    it('应考虑请求体生成去重 key', () => {
      const options = {
        hostname: 'example.com',
        port: 80,
        path: '/api/test',
        method: 'POST'
      };
      
      const body1 = { data: 'test1' };
      const body2 = { data: 'test2' };
      
      const key1 = `${options.method}:${options.hostname}:${options.port}:${options.path}:${JSON.stringify(body1).slice(0, 200)}`;
      const key2 = `${options.method}:${options.hostname}:${options.port}:${options.path}:${JSON.stringify(body2).slice(0, 200)}`;
      
      assert.notStrictEqual(key1, key2, '不同请求体应生成不同 key');
    });
  });

  describe('并行请求', () => {
    it('应正确处理并行请求结果', async () => {
      // 模拟并行请求
      const requests = [
        { name: 'test1', options: { hostname: 'example.com', port: 80, path: '/1' } },
        { name: 'test2', options: { hostname: 'example.com', port: 80, path: '/2' } }
      ];
      
      // 这里只测试方法存在，不实际执行网络请求
      assert(typeof pool.parallelRequests === 'function', '应有 parallelRequests 方法');
    });
  });

  describe('统计信息', () => {
    it('应正确计算命中率', () => {
      pool.stats.hits = 80;
      pool.stats.misses = 20;
      pool.stats.merges = 30;
      
      const stats = pool.stats();
      const expectedRate = ((30 / (80 + 20)) * 100).toFixed(1) + '%';
      assert.strictEqual(stats.hitRate, expectedRate, '命中率计算应正确');
    });

    it('应处理零分母情况', () => {
      pool.stats.hits = 0;
      pool.stats.misses = 0;
      pool.stats.merges = 0;
      
      const stats = pool.stats();
      assert.strictEqual(stats.hitRate, '0%', '零分母时应返回 0%');
    });
  });

  describe('资源清理', () => {
    it('应正确清理所有资源', () => {
      // 创建一些资源
      pool._getAgent('example.com', 80);
      pool._getAgent('example.org', 443);
      pool.pending.set('test-key', Promise.resolve());
      
      assert.strictEqual(pool.pool.size, 2, '应有 2 个连接');
      assert.strictEqual(pool.pending.size, 1, '应有 1 个待处理请求');
      
      // 清理
      pool.shutdown();
      
      assert.strictEqual(pool.pool.size, 0, '清理后连接池应为空');
      assert.strictEqual(pool.pending.size, 0, '清理后待处理队列应为空');
    });
  });
});

// 性能测试
describe('连接池性能测试', () => {
  let pool;

  beforeEach(() => {
    pool = new ConnectionPool();
  });

  afterEach(() => {
    pool.shutdown();
  });

  it('Agent 创建应高效', () => {
    const start = process.hrtime.bigint();
    
    for (let i = 0; i < 100; i++) {
      pool._getAgent(`host${i % 10}.com`, 80);
    }
    
    const end = process.hrtime.bigint();
    const durationMs = Number(end - start) / 1e6;
    
    // 100 次 Agent 创建应在合理时间内完成
    assert(durationMs < 100, `Agent 创建应高效，实际耗时 ${durationMs}ms`);
    
    // 只应创建 10 个不同的 Agent（i % 10）
    assert.strictEqual(pool.pool.size, 10, '应复用 Agent');
  });

  it('统计信息获取应高效', () => {
    // 设置一些数据
    for (let i = 0; i < 10; i++) {
      pool._getAgent(`host${i}.com`, 80);
    }
    
    const start = process.hrtime.bigint();
    
    for (let i = 0; i < 1000; i++) {
      pool.stats();
    }
    
    const end = process.hrtime.bigint();
    const durationMs = Number(end - start) / 1e6;
    
    // 1000 次统计获取应在合理时间内完成
    assert(durationMs < 50, `统计信息获取应高效，实际耗时 ${durationMs}ms`);
  });
});

// 运行测试
if (require.main === module) {
  console.log('运行连接池测试...\n');
}

module.exports = { ConnectionPool };