/**
 * Y·NEX Desktop — Git 管理器
 * 完整 Git 集成：commit / push / branch / blame / history / staging / stash
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class GitManager {
  constructor() {
    this._repoCache = new Map(); // workspacePath -> isRepo
  }

  _exec(workspacePath, args) {
    return new Promise((resolve) => {
      const child = spawn('git', args, {
        cwd: workspacePath,
        windowsHide: true,
        timeout: 30000,
      });
      let stdout = '';
      let stderr = '';
      child.stdout.on('data', (d) => stdout += d.toString());
      child.stderr.on('data', (d) => stderr += d.toString());
      child.on('close', (code) => {
        resolve({ ok: code === 0, code, stdout, stderr });
      });
      child.on('error', (e) => resolve({ ok: false, code: -1, stdout: '', stderr: e.message }));
    });
  }

  isRepo(workspacePath) {
    if (this._repoCache.has(workspacePath)) return this._repoCache.get(workspacePath);
    const gitDir = path.join(workspacePath, '.git');
    const isRepo = fs.existsSync(gitDir);
    this._repoCache.set(workspacePath, isRepo);
    return isRepo;
  }

  async status(workspacePath) {
    return this._exec(workspacePath, ['status', '--porcelain', '-b']);
  }

  async stage(workspacePath, files) {
    const args = ['add', ...(files || ['.'])];
    return this._exec(workspacePath, args);
  }

  async unstage(workspacePath, files) {
    return this._exec(workspacePath, ['reset', 'HEAD', ...(files || [])]);
  }

  async commit(workspacePath, message) {
    return this._exec(workspacePath, ['commit', '-m', message]);
  }

  async push(workspacePath, remote = 'origin', branch = '') {
    const args = ['push', remote];
    if (branch) args.push(branch);
    return this._exec(workspacePath, args);
  }

  async pull(workspacePath, remote = 'origin', branch = '') {
    const args = ['pull', remote];
    if (branch) args.push(branch);
    return this._exec(workspacePath, args);
  }

  async branches(workspacePath) {
    const r = await this._exec(workspacePath, ['branch', '-a', '--format=%(refname:short)']);
    if (!r.ok) return [];
    return r.stdout.trim().split('\n').filter(Boolean);
  }

  async currentBranch(workspacePath) {
    const r = await this._exec(workspacePath, ['rev-parse', '--abbrev-ref', 'HEAD']);
    return r.ok ? r.stdout.trim() : '';
  }

  async checkout(workspacePath, branch) {
    return this._exec(workspacePath, ['checkout', branch]);
  }

  async createBranch(workspacePath, branch) {
    return this._exec(workspacePath, ['checkout', '-b', branch]);
  }

  async deleteBranch(workspacePath, branch) {
    return this._exec(workspacePath, ['branch', '-d', branch]);
  }

  async log(workspacePath, count = 30) {
    const r = await this._exec(workspacePath, [
      'log', `-${count}`, '--oneline', '--decorate', '--graph', '--date=short',
      '--format=%h %s (%an, %ad)'
    ]);
    return r.ok ? r.stdout.trim().split('\n').filter(Boolean) : [];
  }

  async blame(workspacePath, filePath) {
    const r = await this._exec(workspacePath, [
      'blame', '--line-porcelain', filePath
    ]);
    if (!r.ok) return [];
    const lines = [];
    let current = null;
    for (const line of r.stdout.split('\n')) {
      if (line.startsWith('author ')) current = { author: line.substring(7) };
      else if (line.startsWith('committer-time ')) {
        if (current) { current.time = parseInt(line.substring(15)); lines.push({ ...current }); }
      }
    }
    return lines;
  }

  async diff(workspacePath, staged = false) {
    const args = ['diff'];
    if (staged) args.push('--staged');
    return this._exec(workspacePath, args);
  }

  async diffFile(workspacePath, filePath, staged = false) {
    const args = ['diff'];
    if (staged) args.push('--staged');
    args.push('--', filePath);
    return this._exec(workspacePath, args);
  }

  async stash(workspacePath) {
    return this._exec(workspacePath, ['stash']);
  }

  async stashPop(workspacePath) {
    return this._exec(workspacePath, ['stash', 'pop']);
  }

  async stashList(workspacePath) {
    const r = await this._exec(workspacePath, ['stash', 'list']);
    return r.ok ? r.stdout.trim().split('\n').filter(Boolean) : [];
  }

  async remoteStatus(workspacePath) {
    // 先 fetch 获取远程状态
    await this._exec(workspacePath, ['fetch', '--all']);
    const r = await this._exec(workspacePath, ['status', '-sb']);
    return r.ok ? r.stdout : '';
  }

  async init(workspacePath) {
    return this._exec(workspacePath, ['init']);
  }
}

module.exports = { GitManager };