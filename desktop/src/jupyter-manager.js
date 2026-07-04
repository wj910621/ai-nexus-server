/**
 * Y·NEX Desktop — Jupyter 笔记本支持管理器
 * 启动 Jupyter 服务器、创建/管理 .ipynb 文件
 */

const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

class JupyterManager {
  constructor() {
    this.serverProcess = null;
    this.serverUrl = null;
    this.token = null;
    this.port = 8888;
  }

  /**
   * 启动 Jupyter 服务器
   */
  async startServer(workspacePath) {
    if (this.serverProcess) {
      return { ok: true, url: this.serverUrl, running: true };
    }

    return new Promise((resolve) => {
      this.serverProcess = spawn('jupyter', [
        'notebook',
        '--no-browser',
        '--port', String(this.port),
        '--NotebookApp.token=', '',
        '--NotebookApp.password=', '',
        `--notebook-dir=${workspacePath || process.cwd()}`
      ], {
        windowsHide: true,
        stdio: 'pipe'
      });

      let output = '';
      const timeout = setTimeout(() => {
        resolve({ ok: false, error: 'Jupyter 启动超时（请确认已安装 jupyter）' });
      }, 15000);

      this.serverProcess.stdout.on('data', (data) => {
        output += data.toString();
        const match = output.match(/http:\/\/localhost:(\d+)\/\?token=([a-zA-Z0-9]+)/);
        if (match) {
          clearTimeout(timeout);
          this.port = parseInt(match[1]);
          this.token = match[2];
          this.serverUrl = `http://localhost:${this.port}/?token=${this.token}`;
          resolve({ ok: true, url: this.serverUrl, port: this.port, token: this.token });
        }
      });

      this.serverProcess.stderr.on('data', (data) => {
        output += data.toString();
      });

      this.serverProcess.on('error', (err) => {
        clearTimeout(timeout);
        resolve({ ok: false, error: 'Jupyter 未安装: ' + err.message });
      });

      this.serverProcess.on('close', (code) => {
        this.serverProcess = null;
        this.serverUrl = null;
      });
    });
  }

  /**
   * 停止 Jupyter 服务器
   */
  stopServer() {
    if (this.serverProcess) {
      this.serverProcess.kill();
      this.serverProcess = null;
      this.serverUrl = null;
    }
    return { ok: true };
  }

  /**
   * 创建新的 .ipynb 文件
   */
  createNotebook(filePath) {
    const notebook = {
      nbformat: 4,
      nbformat_minor: 5,
      metadata: {
        kernelspec: {
          display_name: 'Python 3',
          language: 'python',
          name: 'python3'
        },
        language_info: {
          name: 'python',
          version: '3.10.0'
        }
      },
      cells: [
        {
          cell_type: 'code',
          metadata: {},
          source: ['# 新笔记本\n'],
          outputs: [],
          execution_count: null
        }
      ]
    };
    fs.writeFileSync(filePath, JSON.stringify(notebook, null, 2), 'utf-8');
    return { ok: true, path: filePath };
  }

  /**
   * 读取 .ipynb 文件并提取所有代码
   */
  readNotebookCode(filePath) {
    try {
      const nb = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      const cells = nb.cells || [];
      const code = cells
        .filter(c => c.cell_type === 'code')
        .map(c => Array.isArray(c.source) ? c.source.join('') : c.source)
        .join('\n\n## Cell\n');
      return { ok: true, code, cellCount: cells.length, codeCells: cells.filter(c => c.cell_type === 'code').length };
    } catch (e) {
      return { error: e.message };
    }
  }

  /**
   * 获取服务器状态
   */
  getStatus() {
    return {
      running: !!this.serverProcess,
      url: this.serverUrl,
      port: this.port
    };
  }
}

module.exports = { JupyterManager };