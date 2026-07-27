/**
 * Y·NEX 增量解析器测试
 * 测试代码符号提取、导入解析和增量更新
 */

const assert = require('assert');
const { IncrementalParser } = require('./desktop/src/incremental-parser');

// 测试套件
describe('增量解析器测试', () => {
  let parser;

  beforeEach(() => {
    parser = new IncrementalParser();
  });

  describe('文件哈希', () => {
    it('应为相同内容生成相同哈希', () => {
      const content = 'test content';
      const hash1 = parser._hash(content);
      const hash2 = parser._hash(content);
      
      assert.strictEqual(hash1, hash2, '相同内容应生成相同哈希');
    });

    it('应为不同内容生成不同哈希', () => {
      const hash1 = parser._hash('content 1');
      const hash2 = parser._hash('content 2');
      
      assert.notStrictEqual(hash1, hash2, '不同内容应生成不同哈希');
    });

    it('应快速计算哈希', () => {
      const content = 'test content'.repeat(1000);
      const start = process.hrtime.bigint();
      
      parser._hash(content);
      
      const end = process.hrtime.bigint();
      const durationMs = Number(end - start) / 1e6;
      
      assert(durationMs < 10, `哈希计算应快速，实际耗时 ${durationMs}ms`);
    });
  });

  describe('Python 符号提取', () => {
    it('应提取函数定义', () => {
      const content = `
def hello():
    pass

def world(name):
    return name
`;
      
      const symbols = parser._extractSymbols(content, 'test.py');
      
      assert.strictEqual(symbols.length, 2, '应提取 2 个函数');
      assert.strictEqual(symbols[0].name, 'hello');
      assert.strictEqual(symbols[0].type, 'function');
      assert.strictEqual(symbols[1].name, 'world');
    });

    it('应提取类定义', () => {
      const content = `
class Person:
    def __init__(self):
        pass

class Animal:
    pass
`;
      
      const symbols = parser._extractSymbols(content, 'test.py');
      
      assert.strictEqual(symbols.length, 2, '应提取 2 个类');
      assert.strictEqual(symbols[0].name, 'Person');
      assert.strictEqual(symbols[0].type, 'class');
      assert.strictEqual(symbols[1].name, 'Animal');
    });

    it('应正确提取行号', () => {
      const content = `# 第一行注释
def test():
    pass
`;
      
      const symbols = parser._extractSymbols(content, 'test.py');
      
      assert.strictEqual(symbols[0].line, 2, '函数应在第 2 行');
    });
  });

  describe('JavaScript/TypeScript 符号提取', () => {
    it('应提取函数声明', () => {
      const content = `
function hello() {
  return 'world';
}

async function asyncFunc() {
  return 'async';
}
`;
      
      const symbols = parser._extractSymbols(content, 'test.js');
      
      assert.strictEqual(symbols.length, 2, '应提取 2 个函数');
      assert.strictEqual(symbols[0].name, 'hello');
      assert.strictEqual(symbols[1].name, 'asyncFunc');
    });

    it('应提取箭头函数', () => {
      const content = `
const add = (a, b) => a + b;
const multiply = async (a, b) => a * b;
`;
      
      const symbols = parser._extractSymbols(content, 'test.js');
      
      assert.strictEqual(symbols.length, 2, '应提取 2 个箭头函数');
      assert.strictEqual(symbols[0].name, 'add');
      assert.strictEqual(symbols[1].name, 'multiply');
    });

    it('应提取类定义', () => {
      const content = `
class Person {
  constructor(name) {
    this.name = name;
  }
}

export class Animal {}
`;
      
      const symbols = parser._extractSymbols(content, 'test.js');
      
      assert.strictEqual(symbols.length, 2, '应提取 2 个类');
      assert.strictEqual(symbols[0].name, 'Person');
      assert.strictEqual(symbols[1].name, 'Animal');
    });

    it('应提取函数表达式', () => {
      const content = `
const fn1 = function() { return 1; };
const fn2 = async function() { return 2; };
`;
      
      const symbols = parser._extractSymbols(content, 'test.js');
      
      assert.strictEqual(symbols.length, 2, '应提取 2 个函数表达式');
      assert.strictEqual(symbols[0].name, 'fn1');
      assert.strictEqual(symbols[1].name, 'fn2');
    });
  });

  describe('导入提取', () => {
    it('应提取 Python 导入', () => {
      const content = `
import os
from sys import path
from collections import defaultdict
`;
      
      const imports = parser._extractImports(content, 'test.py');
      
      assert.strictEqual(imports.length, 3, '应提取 3 个导入');
      assert(imports.includes('os'));
      assert(imports.includes('sys'));
      assert(imports.includes('collections'));
    });

    it('应提取 JavaScript CommonJS 导入', () => {
      const content = `
const fs = require('fs');
const path = require('path');
`;
      
      const imports = parser._extractImports(content, 'test.js');
      
      assert.strictEqual(imports.length, 2, '应提取 2 个导入');
      assert(imports.includes('fs'));
      assert(imports.includes('path'));
    });

    it('应提取 ES6 导入', () => {
      const content = `
import React from 'react';
import { useState, useEffect } from 'react';
import './styles.css';
`;
      
      const imports = parser._extractImports(content, 'test.js');
      
      assert.strictEqual(imports.length, 3, '应提取 3 个导入');
      assert(imports.includes('react'));
      assert(imports.includes('./styles.css'));
    });

    it('应去重导入', () => {
      const content = `
import React from 'react';
import { useState } from 'react';
`;
      
      const imports = parser._extractImports(content, 'test.js');
      
      assert.strictEqual(imports.length, 1, '应去重相同导入');
    });
  });

  describe('增量解析', () => {
    it('应使用缓存处理未变化内容', () => {
      const content = 'def test(): pass';
      
      const result1 = parser.parse('test.py', content);
      const result2 = parser.parse('test.py', content);
      
      assert.strictEqual(result1.cached, false, '首次解析不应缓存');
      assert.strictEqual(result2.cached, true, '再次解析应使用缓存');
      assert.deepStrictEqual(result1.symbols, result2.symbols, '符号应相同');
    });

    it('应更新变化内容', () => {
      const content1 = 'def test(): pass';
      const content2 = 'def test(): pass\n\ndef new(): pass';
      
      parser.parse('test.py', content1);
      const result2 = parser.parse('test.py', content2);
      
      assert.strictEqual(result2.cached, false, '变化内容不应缓存');
      assert.strictEqual(result2.symbols.length, 2, '应提取新符号');
    });

    it('应正确处理 diff', () => {
      const oldContent = 'def old(): pass';
      const newContent = 'def new(): pass';
      const changes = [{ line: 1 }];
      
      const result = parser.parseDiff('test.py', oldContent, newContent, changes);
      
      assert.strictEqual(result.cached, false);
      assert.deepStrictEqual(result.changedLines, [1]);
    });
  });

  describe('Monaco 语言映射', () => {
    it('应正确映射文件扩展名', () => {
      const testCases = [
        { ext: '.js', lang: 'javascript' },
        { ext: '.ts', lang: 'typescript' },
        { ext: '.py', lang: 'python' },
        { ext: '.html', lang: 'html' },
        { ext: '.css', lang: 'css' },
        { ext: '.json', lang: 'json' },
        { ext: '.md', lang: 'markdown' },
        { ext: '.unknown', lang: 'plaintext' }
      ];
      
      testCases.forEach(({ ext, lang }) => {
        const result = parser.getMonacoLanguages(`test${ext}`);
        assert.strictEqual(result.lang, lang, `${ext} 应映射到 ${lang}`);
      });
    });

    it('应首次加载语言模块', () => {
      const result1 = parser.getMonacoLanguages('test.js');
      const result2 = parser.getMonacoLanguages('test.js');
      
      assert.strictEqual(result1.firstLoad, true, '首次应标记为 firstLoad');
      assert.strictEqual(result2.firstLoad, false, '再次加载不应标记');
    });
  });

  describe('依赖图', () => {
    it('应构建依赖图', () => {
      const content = 'import React from "react";\nimport { useState } from "react";';
      parser.parse('test.js', content);
      
      const graph = parser.getDependencyGraph('test.js');
      
      assert.strictEqual(graph.file, 'test.js');
      assert.deepStrictEqual(graph.imports, ['react']);
      assert(Array.isArray(graph.dependents), 'dependents 应为数组');
    });

    it('应处理未解析文件', () => {
      const graph = parser.getDependencyGraph('unknown.js');
      
      assert.strictEqual(graph.file, 'unknown.js');
      assert.deepStrictEqual(graph.imports, []);
      assert.deepStrictEqual(graph.dependents, []);
    });
  });

  describe('统计信息', () => {
    it('应正确统计解析文件数', () => {
      parser.parse('test1.py', 'def test(): pass');
      parser.parse('test2.js', 'function test() {}');
      
      const stats = parser.stats();
      
      assert.strictEqual(stats.parsedFiles, 2, '应统计已解析文件');
    });

    it('应正确统计缓存的符号', () => {
      parser.parse('test.py', 'def test(): pass');
      
      const stats = parser.stats();
      
      assert.strictEqual(stats.cachedSymbols, 1, '应统计缓存的符号');
    });

    it('应正确统计加载的语言数', () => {
      parser.getMonacoLanguages('test.js');
      parser.getMonacoLanguages('test.py');
      
      const stats = parser.stats();
      
      assert.strictEqual(stats.loadedLanguages, 2, '应统计加载的语言');
    });
  });
});

// 性能测试
describe('增量解析器性能测试', () => {
  let parser;

  beforeEach(() => {
    parser = new IncrementalParser();
  });

  it('符号提取应高效', () => {
    const content = Array(100).fill('def test(): pass').join('\n');
    
    const start = process.hrtime.bigint();
    parser._extractSymbols(content, 'test.py');
    const end = process.hrtime.bigint();
    
    const durationMs = Number(end - start) / 1e6;
    assert(durationMs < 50, `符号提取应高效，实际耗时 ${durationMs}ms`);
  });

  it('导入提取应高效', () => {
    const content = Array(100).fill('import test').join('\n');
    
    const start = process.hrtime.bigint();
    parser._extractImports(content, 'test.py');
    const end = process.hrtime.bigint();
    
    const durationMs = Number(end - start) / 1e6;
    assert(durationMs < 50, `导入提取应高效，实际耗时 ${durationMs}ms`);
  });
});

// 运行测试
if (require.main === module) {
  console.log('运行增量解析器测试...\n');
}

module.exports = { IncrementalParser };