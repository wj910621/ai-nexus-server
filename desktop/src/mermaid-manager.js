/**
 * Y·NEX Desktop — Mermaid 图表渲染管理器
 * 将 Mermaid 语法渲染为 SVG
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

class MermaidManager {
  constructor() {
    this.tempDir = path.join(os.tmpdir(), 'ynex-mermaid');
    if (!fs.existsSync(this.tempDir)) {
      fs.mkdirSync(this.tempDir, { recursive: true });
    }
  }

  /**
   * 渲染 Mermaid 图表为 HTML/SVG
   * 使用 mermaid-cli (mmdc) 或纯 JS 渲染
   */
  async render(diagram, { format = 'svg', theme = 'dark' } = {}) {
    const id = `mermaid_${Date.now()}`;
    const inputFile = path.join(this.tempDir, `${id}.mmd`);
    const outputFile = path.join(this.tempDir, `${id}.${format}`);

    // 写入 mermaid 文件
    fs.writeFileSync(inputFile, diagram, 'utf-8');

    try {
      // 尝试使用 mmdc (mermaid-cli)
      const result = await this._renderWithMmdc(inputFile, outputFile, format, theme);
      if (result.ok) {
        return { ok: true, svg: fs.readFileSync(outputFile, 'utf-8'), format, id };
      }
    } catch (e) {}

    // 回退：生成 HTML 页面
    return this._renderAsHtml(diagram, theme, id);
  }

  async _renderWithMmdc(inputFile, outputFile, format, theme) {
    return new Promise((resolve) => {
      const child = spawn('npx', [
        '-y', '@mermaid-js/mermaid-cli', 'mmdc',
        '-i', inputFile,
        '-o', outputFile,
        '-t', theme === 'dark' ? 'dark' : 'default',
        '-b', 'transparent'
      ], { windowsHide: true, timeout: 15000 });

      let stderr = '';
      child.stderr.on('data', d => stderr += d.toString());
      child.on('close', (code) => resolve({ ok: code === 0, stderr }));
      child.on('error', () => resolve({ ok: false, stderr: 'mmdc not available' }));
    });
  }

  _renderAsHtml(diagram, theme, id) {
    const bgColor = theme === 'dark' ? '#0d0d0d' : '#ffffff';
    const textColor = theme === 'dark' ? '#e0e0e0' : '#333333';
    const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js" crossorigin="anonymous"></script>
<script>
// 安全：使用 strict 模式禁止 mermaid 图表中的 HTML 和 click 事件回调，
// 防止 AI 生成的恶意 diagram 在 Electron 渲染进程执行任意 JS。
mermaid.initialize({ startOnLoad: true, theme: '${theme === 'dark' ? 'dark' : 'default'}', securityLevel: 'strict' });
</script>
<style>
body { background: ${bgColor}; color: ${textColor}; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
</style>
</head>
<body>
<div class="mermaid">
${diagram}
</div>
</body>
</html>`;

    const htmlFile = path.join(this.tempDir, `${id}.html`);
    fs.writeFileSync(htmlFile, html, 'utf-8');
    return { ok: true, html: `file:///${htmlFile.replace(/\\/g, '/')}`, format: 'html', id };
  }

  /**
   * 从代码生成流程图
   */
  async generateFlowchart(code, language) {
    const prompt = `请分析以下代码的函数调用关系，生成 Mermaid flowchart 格式的流程图。

语言: ${language}

\`\`\`${language}
${code.slice(0, 4000)}
\`\`\`

只输出 Mermaid 代码（在 \`\`\`mermaid 代码块中），不要其他内容。使用 flowchart TD 格式。`;

    // 使用本地 ynex API
    try {
      const http = require('http');
      const result = await new Promise((resolve) => {
        const data = JSON.stringify({
          messages: [{ role: 'user', content: prompt }],
          max_tokens: 2048,
          temperature: 0.2
        });
        const req = http.request({
          hostname: '127.0.0.1',
          port: 7777,
          path: '/api/chat/stream',
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) },
          timeout: 30000
        }, (res) => {
          let response = '';
          res.on('data', d => response += d);
          res.on('end', () => resolve(response));
        });
        req.on('error', () => resolve(''));
        req.on('timeout', () => { req.destroy(); resolve(''); });
        req.write(data);
        req.end();
      });

      const match = (typeof result === 'string' ? result : '').match(/```mermaid\n?([\s\S]*?)\n?```/);
      if (match) {
        return { ok: true, diagram: match[1].trim() };
      }
    } catch (e) {}

    return { ok: false, error: '无法生成流程图' };
  }

  /**
   * 生成类图
   */
  async generateClassDiagram(code, language) {
    const prompt = `请分析以下代码的类/接口/结构体定义，生成 Mermaid classDiagram 格式的类图。

语言: ${language}

\`\`\`${language}
${code.slice(0, 4000)}
\`\`\`

只输出 Mermaid 代码（在 \`\`\`mermaid 代码块中），不要其他内容。`;

    try {
      const http = require('http');
      const result = await new Promise((resolve) => {
        const data = JSON.stringify({
          messages: [{ role: 'user', content: prompt }],
          max_tokens: 2048,
          temperature: 0.2
        });
        const req = http.request({
          hostname: '127.0.0.1',
          port: 7777,
          path: '/api/chat/stream',
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) },
          timeout: 30000
        }, (res) => {
          let response = '';
          res.on('data', d => response += d);
          res.on('end', () => resolve(response));
        });
        req.on('error', () => resolve(''));
        req.on('timeout', () => { req.destroy(); resolve(''); });
        req.write(data);
        req.end();
      });

      const match = (typeof result === 'string' ? result : '').match(/```mermaid\n?([\s\S]*?)\n?```/);
      if (match) {
        return { ok: true, diagram: match[1].trim() };
      }
    } catch (e) {}

    return { ok: false, error: '无法生成类图' };
  }
}

module.exports = { MermaidManager };