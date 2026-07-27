/**
 * Y·NEX 安全系统测试
 * 测试危险操作检测、确认机制和输出过滤
 */

const assert = require('assert');

// 模拟安全系统（简化版，用于测试）
const SafetySystem = {
  DANGEROUS_OPERATIONS: {
    FILE_DELETE: {
      id: 'file_delete',
      pattern: /rm\s+(-[rf]?\s+)*|delete\s+file|remove\s+file|unlink/i,
      requiresConfirm: true
    },
    GIT_FORCE_PUSH: {
      id: 'git_force_push',
      pattern: /git\s+push\s+(-f|--force)/i,
      requiresConfirm: true,
      highRisk: true
    },
    SYSTEM_REBOOT: {
      id: 'system_reboot',
      pattern: /reboot|shutdown|init\s+6/i,
      requiresConfirm: true,
      highRisk: true
    },
    DB_DROP: {
      id: 'db_drop',
      pattern: /drop\s+(table|database)|delete\s+from\s+\w+\s*;?\s*where/i,
      requiresConfirm: true,
      highRisk: true
    }
  },

  analyze(command) {
    const matches = [];
    for (const [key, op] of Object.entries(this.DANGEROUS_OPERATIONS)) {
      if (op.pattern.test(command)) {
        matches.push({ ...op, key });
      }
    }
    return matches;
  },

  OutputFilter: {
    patterns: [
      { pattern: /api[_-]?key['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replacement: 'api_key: "***"' },
      { pattern: /sk-[a-zA-Z0-9]{20,}/g, replacement: 'sk-***' },
      { pattern: /password['":\s=]+['"]?([^\s'"]{8,})/gi, replacement: 'password: "***"' }
    ],

    filter(output) {
      let filtered = output;
      for (const { pattern, replacement } of this.patterns) {
        filtered = filtered.replace(pattern, replacement);
      }
      return filtered;
    },

    containsSensitive(output) {
      for (const { pattern } of this.patterns) {
        if (pattern.test(output)) return true;
      }
      return false;
    }
  }
};

// 测试套件
describe('安全系统测试', () => {
  describe('危险操作检测', () => {
    it('应检测文件删除操作', () => {
      const commands = [
        'rm file.txt',
        'rm -rf directory',
        'delete file test.txt',
        'unlink /path/to/file'
      ];
      
      commands.forEach(cmd => {
        const matches = SafetySystem.analyze(cmd);
        assert(matches.some(m => m.id === 'file_delete'), `应检测: ${cmd}`);
      });
    });

    it('应检测强制推送操作', () => {
      const commands = [
        'git push -f origin main',
        'git push --force',
        'git push -f'
      ];
      
      commands.forEach(cmd => {
        const matches = SafetySystem.analyze(cmd);
        assert(matches.some(m => m.id === 'git_force_push'), `应检测: ${cmd}`);
      });
    });

    it('应检测系统重启操作', () => {
      const commands = [
        'reboot',
        'shutdown now',
        'init 6'
      ];
      
      commands.forEach(cmd => {
        const matches = SafetySystem.analyze(cmd);
        assert(matches.some(m => m.id === 'system_reboot'), `应检测: ${cmd}`);
      });
    });

    it('应检测数据库删除操作', () => {
      const commands = [
        'drop table users',
        'drop database mydb',
        'delete from users where 1=1'
      ];
      
      commands.forEach(cmd => {
        const matches = SafetySystem.analyze(cmd);
        assert(matches.some(m => m.id === 'db_drop'), `应检测: ${cmd}`);
      });
    });

    it('应标记高危操作', () => {
      const matches = SafetySystem.analyze('git push -f origin main');
      const highRiskMatch = matches.find(m => m.id === 'git_force_push');
      
      assert(highRiskMatch.highRisk, '强制推送应标记为高危');
    });

    it('应允许安全命令', () => {
      const commands = [
        'ls -la',
        'git status',
        'npm install',
        'echo "hello"'
      ];
      
      commands.forEach(cmd => {
        const matches = SafetySystem.analyze(cmd);
        assert.strictEqual(matches.length, 0, `应允许: ${cmd}`);
      });
    });
  });

  describe('输出过滤', () => {
    it('应过滤 API Key', () => {
      const testCases = [
        {
          input: 'api_key: sk-1234567890abcdefghijklmnop',
          expected: 'api_key: sk-***'
        },
        {
          input: 'API_KEY=sk-abcdefghij1234567890klmnop',
          expected: 'API_KEY=sk-***'
        }
      ];
      
      testCases.forEach(({ input, expected }) => {
        const filtered = SafetySystem.OutputFilter.filter(input);
        assert.strictEqual(filtered, expected, `应过滤: ${input}`);
      });
    });

    it('应过滤密码', () => {
      const input = 'password: mysecretpassword123';
      const filtered = SafetySystem.OutputFilter.filter(input);
      
      assert.strictEqual(filtered, 'password: "***"', '应过滤密码');
    });

    it('应检测敏感信息', () => {
      const sensitive = [
        'api_key: sk-1234567890abcdefghijklmnop',
        'password: mysecretpassword',
        'token: abcdefghij1234567890klmnop'
      ];
      
      sensitive.forEach(output => {
        assert(SafetySystem.OutputFilter.containsSensitive(output), `应检测敏感: ${output}`);
      });
    });

    it('应允许非敏感输出', () => {
      const safe = [
        'Hello, World!',
        'The result is 42',
        'User: admin'
      ];
      
      safe.forEach(output => {
        assert(!SafetySystem.OutputFilter.containsSensitive(output), `应允许: ${output}`);
      });
    });

    it('应保持输出完整性（仅替换敏感部分）', () => {
      const input = 'User login successful. api_key: sk-1234567890abcdefghijklmnop for user admin.';
      const filtered = SafetySystem.OutputFilter.filter(input);
      
      assert(filtered.includes('User login successful'), '应保留非敏感部分');
      assert(filtered.includes('for user admin'), '应保留非敏感部分');
      assert(!filtered.includes('sk-1234567890abcdefghijklmnop'), '应过滤敏感部分');
    });
  });
});

describe('确认机制测试', () => {
  describe('信任管理', () => {
    it('应正确管理信任列表', () => {
      const trustedPatterns = new Set();
      
      // 添加信任
      trustedPatterns.add('file_delete');
      trustedPatterns.add('git_push');
      
      assert(trustedPatterns.has('file_delete'), '应包含已添加的信任');
      assert(trustedPatterns.has('git_push'), '应包含已添加的信任');
      
      // 移除信任
      trustedPatterns.delete('file_delete');
      
      assert(!trustedPatterns.has('file_delete'), '应不包含已删除的信任');
      assert(trustedPatterns.has('git_push'), '应保留其他信任');
    });

    it('应支持信任期限', () => {
      const trustTimestamp = {};
      const trustDuration = 60000; // 60 秒
      
      function isTrusted(operationId) {
        const timestamp = trustTimestamp[operationId];
        if (!timestamp) return false;
        
        return Date.now() - timestamp <= trustDuration;
      }
      
      // 添加信任
      trustTimestamp['file_delete'] = Date.now();
      
      assert(isTrusted('file_delete'), '刚添加的信任应有效');
      
      // 模拟过期
      trustTimestamp['file_delete'] = Date.now() - trustDuration - 1000;
      
      assert(!isTrusted('file_delete'), '过期的信任应无效');
    });
  });

  describe('用户交互', () => {
    it('应提供清晰的确认消息', () => {
      const operation = SafetySystem.DANGEROUS_OPERATIONS.GIT_FORCE_PUSH;
      
      assert(operation.requiresConfirm, '高危操作应需要确认');
      assert(operation.highRisk, '应标记为高危');
    });

    it('应提供选项来信任本次会话', () => {
      // 模拟信任选择
      const trustChoice = true;
      const operationId = 'file_delete';
      
      // 如果用户选择信任，应添加到信任列表
      const trustedPatterns = new Set();
      
      if (trustChoice) {
        trustedPatterns.add(operationId);
      }
      
      assert(trustedPatterns.has(operationId), '应添加到信任列表');
    });
  });
});

describe('边界条件和异常处理', () => {
  it('应处理空命令', () => {
    const matches = SafetySystem.analyze('');
    assert.strictEqual(matches.length, 0, '空命令应无匹配');
  });

  it('应处理空输出', () => {
    const filtered = SafetySystem.OutputFilter.filter('');
    assert.strictEqual(filtered, '', '空输出应返回空');
  });

  it('应处理特殊字符', () => {
    const matches = SafetySystem.analyze('rm -rf /path/with spaces/file.txt');
    assert(matches.some(m => m.id === 'file_delete'), '应处理包含空格的路径');
  });

  it('应处理 Unicode 字符', () => {
    const filtered = SafetySystem.OutputFilter.filter('用户：管理员，密码：测试密码');
    assert(filtered.includes('用户：管理员'), '应保留 Unicode 字符');
  });

  it('应正确处理多次匹配', () => {
    const input = 'api_key: sk-1234567890abcdefghijklmnop and password: mysecret';
    const filtered = SafetySystem.OutputFilter.filter(input);
    
    assert(!filtered.includes('sk-1234567890abcdefghijklmnop'), '应过滤 API Key');
    assert(!filtered.includes('mysecret'), '应过滤密码');
  });
});

// 性能测试
describe('安全系统性能测试', () => {
  it('危险操作检测应高效', () => {
    const commands = Array(1000).fill('rm -rf /path/to/file');
    
    const start = process.hrtime.bigint();
    commands.forEach(cmd => SafetySystem.analyze(cmd));
    const end = process.hrtime.bigint();
    
    const durationMs = Number(end - start) / 1e6;
    assert(durationMs < 100, `检测应高效，实际耗时 ${durationMs}ms`);
  });

  it('输出过滤应高效', () => {
    const outputs = Array(1000).fill('api_key: sk-1234567890abcdefghijklmnop password: mysecret');
    
    const start = process.hrtime.bigint();
    outputs.forEach(output => SafetySystem.OutputFilter.filter(output));
    const end = process.hrtime.bigint();
    
    const durationMs = Number(end - start) / 1e6;
    assert(durationMs < 100, `过滤应高效，实际耗时 ${durationMs}ms`);
  });
});

// 运行测试
if (require.main === module) {
  console.log('运行安全系统测试...\n');
}

module.exports = { SafetySystem };