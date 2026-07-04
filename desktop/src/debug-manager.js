/**
 * Y·NEX Desktop — DAP 调试器管理器
 * 通过 Debug Adapter Protocol 实现断点调试
 * 支持 Python (debugpy) 和 Node.js (内置 inspector)
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const net = require('net');

class DebugManager {
  constructor() {
    this.sessions = new Map(); // id -> { proc, port, breakpoints, stdout, state }
    this._nextId = 1;
    this._nextPort = 5678;
  }

  /**
   * 启动 Python 调试会话
   */
  async startPython(scriptPath, workspacePath, breakpoints = []) {
    const port = this._nextPort++;
    const id = `py-${this._nextId++}`;

    const proc = spawn('python', ['-m', 'debugpy', '--listen', String(port), scriptPath], {
      cwd: workspacePath || process.cwd(),
      windowsHide: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    const session = {
      id,
      type: 'python',
      proc,
      port,
      breakpoints: breakpoints.map(bp => ({ file: bp.file, line: bp.line, verified: false })),
      state: 'waiting', // waiting | running | paused | stopped
      stdout: '',
      onOutput: null,
      onStop: null,
    };

    proc.stdout.on('data', (d) => {
      session.stdout += d.toString();
      if (session.onOutput) session.onOutput(d.toString());
    });
    proc.stderr.on('data', (d) => {
      session.stdout += d.toString();
      if (session.onOutput) session.onOutput(d.toString());
    });
    proc.on('close', (code) => {
      session.state = 'stopped';
      if (session.onStop) session.onStop(code);
    });

    this.sessions.set(id, session);

    // 等待 debugpy 就绪
    await new Promise(r => setTimeout(r, 1500));

    // 连接调试适配器
    try {
      await this._connectDAP(port, breakpoints);
      session.state = 'running';
    } catch (e) {
      session.state = 'stopped';
      session.stdout += `\n调试连接失败: ${e.message}`;
    }

    return id;
  }

  /**
   * 启动 Node.js 调试会话
   */
  async startNode(scriptPath, workspacePath, breakpoints = []) {
    const port = this._nextPort++;
    const id = `node-${this._nextId++}`;

    const proc = spawn('node', ['--inspect-brk=' + port, scriptPath], {
      cwd: workspacePath || process.cwd(),
      windowsHide: true,
    });

    const session = {
      id,
      type: 'node',
      proc,
      port,
      breakpoints: breakpoints.map(bp => ({ file: bp.file, line: bp.line, verified: false })),
      state: 'waiting',
      stdout: '',
      onOutput: null,
      onStop: null,
    };

    proc.stdout.on('data', (d) => {
      session.stdout += d.toString();
      if (session.onOutput) session.onOutput(d.toString());
    });
    proc.stderr.on('data', (d) => {
      session.stdout += d.toString();
      if (session.onOutput) session.onOutput(d.toString());
    });
    proc.on('close', (code) => {
      session.state = 'stopped';
      if (session.onStop) session.onStop(code);
    });

    this.sessions.set(id, session);
    return id;
  }

  /**
   * 连接到 DAP 端口并设置断点
   */
  async _connectDAP(port, breakpoints) {
    return new Promise((resolve, reject) => {
      const socket = new net.Socket();
      let buffer = '';
      const timeout = setTimeout(() => {
        socket.destroy();
        reject(new Error('DAP 连接超时'));
      }, 5000);

      socket.connect(port, '127.0.0.1', () => {
        clearTimeout(timeout);
        // 发送 initialize
        this._sendDAP(socket, {
          type: 'request',
          seq: 1,
          command: 'initialize',
          arguments: {
            clientID: 'ynex-desktop',
            clientName: 'Y·NEX Desktop',
            adapterID: 'python',
            linesStartAt1: true,
            columnsStartAt1: true,
          }
        });

        // 设置断点
        for (const bp of breakpoints) {
          this._sendDAP(socket, {
            type: 'request',
            seq: this._nextId++,
            command: 'setBreakpoints',
            arguments: {
              source: { path: bp.file },
              breakpoints: [{ line: bp.line }]
            }
          });
        }

        // 启动
        this._sendDAP(socket, {
          type: 'request',
          seq: this._nextId++,
          command: 'configurationDone',
          arguments: {}
        });

        socket.destroy();
        resolve();
      });

      socket.on('error', (e) => {
        clearTimeout(timeout);
        reject(e);
      });
    });
  }

  _sendDAP(socket, msg) {
    const body = JSON.stringify(msg);
    const header = `Content-Length: ${Buffer.byteLength(body, 'utf-8')}\r\n\r\n`;
    socket.write(header + body);
  }

  /**
   * 获取会话输出
   */
  getOutput(id) {
    const session = this.sessions.get(id);
    if (!session) return { ok: false, error: '会话不存在' };
    return { ok: true, output: session.stdout, state: session.state };
  }

  /**
   * 停止调试会话
   */
  stop(id) {
    const session = this.sessions.get(id);
    if (!session) return { ok: false, error: '会话不存在' };
    try {
      session.proc.kill();
      session.state = 'stopped';
    } catch (e) {}
    this.sessions.delete(id);
    return { ok: true };
  }

  /**
   * 列出所有会话
   */
  list() {
    return Array.from(this.sessions.entries()).map(([id, s]) => ({
      id, type: s.type, state: s.state, port: s.port
    }));
  }

  shutdown() {
    for (const [id, session] of this.sessions.entries()) {
      try { session.proc.kill(); } catch (e) {}
    }
    this.sessions.clear();
  }
}

module.exports = { DebugManager };