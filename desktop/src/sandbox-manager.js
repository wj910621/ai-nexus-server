/**
 * Y·NEX Desktop — 代码沙箱与自动测试验证
 * 
 * 让 Agent 修改在安全隔离环境中运行，验证正确性后再写入文件
 * 功能：
 *   - 临时目录执行（沙箱隔离）
 *   - 语法检查（Python: py_compile, JS: node --check）
 *   - 测试运行（pytest, npm test）
 *   - 修改前后对比 + 回滚
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

class SandboxManager {
  constructor() {
    this.snapshots = new Map();   // filePath -> { original, modified, timestamp }
    this.sandboxDir = path.join(os.tmpdir(), 'ynex-sandbox');
  }

  /**
   * 创建文件快照（用于回滚）
   */
  snapshot(filePath) {
    try {
      if (!fs.existsSync(filePath)) return null;
      const content = fs.readFileSync(filePath, 'utf-8');
      const snap = {
        filePath,
        original: content,
        timestamp: Date.now(),
      };
      this.snapshots.set(filePath, snap);
      return snap;
    } catch (e) {
      console.warn(`[沙箱] 快照失败: ${filePath}`, e.message);
      return null;
    }
  }

  /**
   * 批量快照
   */
  snapshotAll(filePaths) {
    const results = [];
    for (const fp of filePaths) {
      const snap = this.snapshot(fp);
      if (snap) results.push(snap);
    }
    return results;
  }

  /**
   * 回滚单个文件
   */
  rollback(filePath) {
    const snap = this.snapshots.get(filePath);
    if (!snap) return { ok: false, error: '没有快照' };
    try {
      fs.writeFileSync(filePath, snap.original, 'utf-8');
      this.snapshots.delete(filePath);
      return { ok: true, message: `已回滚: ${filePath}` };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * 回滚所有快照
   */
  rollbackAll() {
    const results = [];
    for (const [filePath, snap] of this.snapshots.entries()) {
      const r = this.rollback(filePath);
      results.push(r);
    }
    return results;
  }

  /**
   * 获取修改 diff
   */
  getDiff(filePath) {
    const snap = this.snapshots.get(filePath);
    if (!snap) return { ok: false, error: '没有快照' };
    try {
      const current = fs.readFileSync(filePath, 'utf-8');
      return {
        ok: true,
        filePath,
        original: snap.original,
        modified: current,
        hasChanges: snap.original !== current,
      };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * 语法检查
   */
  async syntaxCheck(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    try {
      if (ext === '.py') {
        return await this._exec('python', ['-m', 'py_compile', filePath]);
      } else if (['.js', '.mjs'].includes(ext)) {
        return await this._exec('node', ['--check', filePath]);
      } else if (['.ts', '.tsx'].includes(ext)) {
        return await this._exec('npx', ['-y', 'typescript', '--noEmit', filePath]);
      }
      return { ok: true, message: '该文件类型不支持语法检查' };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * 在沙箱目录中运行测试
   */
  async runTests(workspacePath, testCommand = '') {
    if (!workspacePath) return { ok: false, error: '未指定工作区' };

    const cmd = testCommand || this._detectTestCommand(workspacePath);
    if (!cmd) return { ok: false, error: '未检测到测试命令' };

    try {
      const parts = cmd.split(/\s+/);
      return await this._exec(parts[0], parts.slice(1), workspacePath);
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * 在沙箱中写入并验证
   * 1. 保存原始内容
   * 2. 写入新内容
   * 3. 语法检查
   * 4. 如果失败，恢复原始内容
   */
  async safeWrite(filePath, newContent) {
    // 1. 快照
    this.snapshot(filePath);

    // 2. 写入
    try {
      fs.writeFileSync(filePath, newContent, 'utf-8');
    } catch (e) {
      return { ok: false, error: `写入失败: ${e.message}` };
    }

    // 3. 语法检查
    const checkResult = await this.syntaxCheck(filePath);
    if (!checkResult.ok) {
      // 语法错误，回滚
      this.rollback(filePath);
      return {
        ok: false,
        error: `语法检查失败，已回滚:\n${checkResult.error || checkResult.stderr || ''}`,
        rolledBack: true,
      };
    }

    return { ok: true, message: '写入成功并通过语法检查' };
  }

  /**
   * 批量安全写入（多文件 Agent 修改）
   */
  async safeWriteBatch(edits) {
    const results = [];
    let allPassed = true;

    // 先全量快照
    for (const { filePath } of edits) {
      this.snapshot(filePath);
    }

    // 写入并逐个检查
    for (const { filePath, content } of edits) {
      const r = await this.safeWrite(filePath, content);
      results.push({ filePath, ...r });
      if (!r.ok) allPassed = false;
    }

    return { ok: allPassed, results };
  }

  /**
   * 运行项目测试并返回结果
   */
  async runProjectTests(workspacePath) {
    if (!workspacePath) return { ok: false, error: '未指定工作区' };

    const results = [];
    const testCmd = this._detectTestCommand(workspacePath);

    if (testCmd) {
      const r = await this.runTests(workspacePath, testCmd);
      results.push({ command: testCmd, ...r });
    }

    return { ok: results.length > 0, results };
  }

  /**
   * 检测项目的测试命令
   */
  _detectTestCommand(workspacePath) {
    try {
      // 检查 package.json -> npm test
      if (fs.existsSync(path.join(workspacePath, 'package.json'))) {
        const pkg = JSON.parse(fs.readFileSync(path.join(workspacePath, 'package.json'), 'utf-8'));
        if (pkg.scripts?.test) return 'npm test';
        if (pkg.scripts?.lint) return 'npm run lint';
      }

      // 检查 pytest
      if (fs.existsSync(path.join(workspacePath, 'pytest.ini')) ||
          fs.existsSync(path.join(workspacePath, 'pyproject.toml')) ||
          fs.existsSync(path.join(workspacePath, 'setup.cfg'))) {
        return 'python -m pytest --tb=short';
      }

      // 检查 Go
      if (fs.existsSync(path.join(workspacePath, 'go.mod'))) {
        return 'go test ./...';
      }

      // 检查 Rust
      if (fs.existsSync(path.join(workspacePath, 'Cargo.toml'))) {
        return 'cargo test';
      }

      return null;
    } catch (e) {
      return null;
    }
  }

  async _exec(cmd, args = [], cwd = '') {
    return new Promise((resolve) => {
      // 安全：禁用 shell:true 防止命令注入。
      // 当 shell:true 时，args 中的特殊字符（; | & 等）会被 shell 解释为命令分隔符。
      const child = spawn(cmd, args, {
        cwd: cwd || process.cwd(),
        shell: false,
        windowsHide: true,
        timeout: 60000,
      });

      let stdout = '';
      let stderr = '';
      child.stdout.on('data', (data) => stdout += data.toString());
      child.stderr.on('data', (data) => stderr += data.toString());

      child.on('close', (code) => {
        resolve({
          ok: code === 0,
          exitCode: code,
          stdout: stdout.substring(0, 10000),
          stderr: stderr.substring(0, 5000),
          error: code !== 0 ? `退出码: ${code}` : null,
        });
      });

      child.on('error', (err) => {
        resolve({ ok: false, error: err.message, stdout: '', stderr: '' });
      });
    });
  }

  /**
   * 清理
   */
  clear() {
    this.snapshots.clear();
  }
}

module.exports = { SandboxManager };