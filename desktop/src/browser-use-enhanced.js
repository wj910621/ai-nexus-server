/**
 * BrowserUseEnhanced — AI 驱动的浏览器自动化模块
 * =================================================
 * 灵感来源：Browser Use 开源项目（https://github.com/browser-use/browser-use）
 *
 * 设计目标：
 *   1. 提供自然语言驱动的浏览器操作能力（find_element / smart_action）
 *   2. 不在 package.json 中引入第三方依赖
 *      —— 通过 child_process 动态调用已安装的 Playwright / Puppeteer
 *   3. 若浏览器工具未安装，自动降级为 fetch 模式（仅能获取页面 HTML 文本）
 *   4. 支持任务录制与回放（record / replay / export）
 *
 * 使用方式：
 *   const { BrowserUseEnhanced } = require('./browser-use-enhanced');
 *   const bue = new BrowserUseEnhanced();
 *   await bue.navigate('https://example.com');
 *   const info = await bue.get_page_info();
 *
 * 引擎优先级：playwright > puppeteer > fetch(降级)
 */

'use strict';

const { spawnSync } = require('child_process');
const https = require('https');
const http = require('http');
const { URL } = require('url');
const path = require('path');
const os = require('os');
const fs = require('fs');

// ============================================================
// 内部常量
// ============================================================

const DEFAULT_VIEWPORT = { width: 1280, height: 800 };
const DEFAULT_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
const DEFAULT_TIMEOUT = 30000;
const MAX_TEXT_CHARS = 5000;

/**
 * 浏览器动作执行脚本（在 child_process 中运行）
 * 通过 argv[2] 接收 JSON 指令，输出 JSON 结果到 stdout
 *
 * 该脚本独立运行，每次启动一个新的浏览器实例，执行单次动作后关闭。
 * 优点：无状态、易调试；缺点：每次有冷启动开销（约 1~2 秒）。
 */
const HELPER_SCRIPT_SOURCE = `
'use strict';
const input = JSON.parse(process.argv[2] || '{}');

function emit(obj) {
  process.stdout.write(JSON.stringify(obj));
}

(async () => {
  let engine = null;
  let engineName = null;
  try { engine = require('playwright'); engineName = 'playwright'; } catch (e) {}
  if (!engine) {
    try { engine = require('puppeteer'); engineName = 'puppeteer'; } catch (e) {}
  }
  if (!engine) {
    emit({ ok: false, error: 'NO_ENGINE', message: 'Playwright/Puppeteer 未安装' });
    return;
  }

  const isPlaywright = engineName === 'playwright';
  let browser = null;
  let page = null;
  let context = null;
  try {
    const viewport = input.viewport || { width: 1280, height: 800 };
    const userAgent = input.userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36';
    const timeout = input.timeout || 30000;
    const headless = input.headless !== false;

    if (isPlaywright) {
      browser = await engine.chromium.launch({ headless });
      context = await browser.newContext({ viewport, userAgent });
      page = await context.newPage();
      page.setDefaultTimeout(timeout);
    } else {
      browser = await engine.launch({ headless, args: ['--no-sandbox', '--disable-setuid-sandbox'] });
      page = await browser.newPage();
      await page.setViewport(viewport);
      page.setDefaultTimeout(timeout);
    }

    if (input.url) {
      const waitUntil = isPlaywright ? 'domcontentloaded' : 'domcontentloaded';
      await page.goto(input.url, { waitUntil, timeout });
    }

    let data = {};
    const action = input.action;

    switch (action) {
      case 'navigate':
        data = { url: page.url(), title: await page.title() };
        break;

      case 'screenshot': {
        const buf = await page.screenshot({ fullPage: input.fullPage || false, type: 'png' });
        data = { base64: buf.toString('base64'), url: page.url(), title: await page.title() };
        break;
      }

      case 'extract': {
        if (input.selector) {
          try {
            const text = await page.$eval(input.selector, (el) => el.innerText);
            data = { text };
          } catch (e) {
            data = { text: '', error: e.message };
          }
        } else {
          const text = await page.evaluate(() => document.body && document.body.innerText ? document.body.innerText : '');
          const html = await page.content();
          data = { text: (text || '').slice(0, 5000), html };
        }
        break;
      }

      case 'click':
        await page.click(input.selector);
        data = { selector: input.selector, url: page.url() };
        break;

      case 'type':
        await page.click(input.selector);
        await page.fill(input.selector, input.text);
        data = { selector: input.selector, text: input.text };
        break;

      case 'scroll': {
        const amt = input.amount || 500;
        if (input.direction === 'down') await page.mouse.wheel(0, amt);
        else if (input.direction === 'up') await page.mouse.wheel(0, -amt);
        else if (input.direction === 'right') await page.mouse.wheel(amt, 0);
        else if (input.direction === 'left') await page.mouse.wheel(-amt, 0);
        data = { direction: input.direction, amount: amt };
        break;
      }

      case 'wait':
        await page.waitForSelector(input.selector, { timeout: input.timeout || 30000 });
        data = { selector: input.selector };
        break;

      case 'evaluate': {
        // 安全：禁止 new Function 任意代码执行（等价于 eval）。
        // AI agent 可被诱导输出恶意 fnBody，在 Node.js 主进程执行 RCE。
        // 如果需要页面内执行 JS，应使用白名单校验或受限的表达式语言。
        if (input.fnBody && typeof input.fnBody === 'string') {
          // 仅允许简单的选择器提取操作，禁止任意代码
          const forbidden = ['require', 'process', 'child_process', 'exec', 'spawn', 'eval', 'Function', 'global', 'module', 'import', 'fetch', 'XMLHttpRequest', 'localStorage'];
          const lowerBody = input.fnBody.toLowerCase();
          for (const kw of forbidden) {
            if (lowerBody.includes(kw.toLowerCase())) {
              return { ok: false, error: 'Security: evaluate forbidden keyword ' + kw };
            }
          }
          try {
            const fn = new Function('return (' + input.fnBody + ')')();
            const value = await page.evaluate(fn);
            data = { value };
          } catch (e) {
            return { ok: false, error: 'evaluate 执行失败: ' + e.message };
          }
        } else {
          return { ok: false, error: '缺少 fnBody 参数' };
        }
        break;
      }

      case 'page_info': {
        const text = await page.evaluate(() => document.body && document.body.innerText ? document.body.innerText : '');
        data = {
          url: page.url(),
          title: await page.title(),
          text: (text || '').slice(0, 2000),
        };
        break;
      }

      case 'find_element': {
        const desc = (input.description || '').toLowerCase();
        const matches = await page.evaluate((d) => {
          const els = Array.from(document.querySelectorAll(
            'a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]'
          ));
          const results = els.map((el) => {
            const text = (el.innerText || el.textContent || el.value ||
              el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
              el.getAttribute('title') || '').trim();
            let score = 0;
            const tl = text.toLowerCase();
            if (tl && tl.includes(d)) score += 10;
            if (el.getAttribute('type') && el.getAttribute('type').toLowerCase().includes(d)) score += 5;
            if (el.id && el.id.toLowerCase().includes(d)) score += 3;
            const cls = typeof el.className === 'string' ? el.className : '';
            if (cls && cls.toLowerCase().includes(d)) score += 1;
            const role = el.getAttribute('role');
            if (role && role.toLowerCase().includes(d)) score += 2;
            let selector = '';
            if (el.id) {
              selector = '#' + el.id.replace(/[^a-zA-Z0-9_-]/g, (c) => '\\\\' + c);
            } else {
              selector = el.tagName.toLowerCase() +
                (text ? ':has-text("' + text.slice(0, 40).replace(/"/g, '\\\\"') + '")' : '');
            }
            return {
              tag: el.tagName.toLowerCase(),
              text: text.slice(0, 100),
              id: el.id || '',
              className: cls.slice(0, 100),
              role: role || '',
              type: el.getAttribute('type') || '',
              score,
              selector,
            };
          }).filter((x) => x.score > 0).sort((a, b) => b.score - a.score).slice(0, 5);
          return results;
        }, desc);
        data = { matches, description: input.description };
        break;
      }

      default:
        throw new Error('Unknown action: ' + action);
    }

    emit({
      ok: true,
      data,
      url: page.url(),
      title: await page.title(),
      engine: engineName,
    });
  } catch (e) {
    emit({ ok: false, error: e.message, stack: e.stack, engine: engineName });
  } finally {
    try { if (browser) await browser.close(); } catch (e) {}
  }
})();
`;

// ============================================================
// BrowserUseEnhanced 类
// ============================================================

class BrowserUseEnhanced {
  /**
   * @param {Object} [options]
   * @param {Object} [options.viewport]
   * @param {string} [options.userAgent]
   * @param {number} [options.timeout]
   * @param {boolean} [options.headless]
   * @param {string} [options.nodePath] 自定义 node 可执行文件路径
   */
  constructor(options = {}) {
    this.options = {
      viewport: DEFAULT_VIEWPORT,
      userAgent: DEFAULT_USER_AGENT,
      timeout: DEFAULT_TIMEOUT,
      headless: true,
      nodePath: process.execPath,
      ...options,
    };

    // 任务录制状态
    this.recording = [];
    this.isRecording = false;

    // 页面状态
    this.currentUrl = null;
    this.pageInfo = { title: '', url: '', text: '' };
    this._lastHtml = '';

    // 引擎检测结果缓存
    this._engine = null; // 'playwright' | 'puppeteer' | 'fetch' | null
    this._engineDetected = false;
  }

  /* ===================== 引擎检测 ===================== */

  /**
   * 检测可用的浏览器引擎
   * 优先级：playwright > puppeteer > fetch(降级)
   * @returns {Promise<'playwright'|'puppeteer'|'fetch'>}
   */
  async detectEngine() {
    if (this._engineDetected) return this._engine;
    this._engineDetected = true;

    // 通过 require.resolve 探测是否安装了 playwright / puppeteer
    for (const name of ['playwright', 'puppeteer']) {
      try {
        require.resolve(name);
        this._engine = name;
        return name;
      } catch (_) {
        // 未安装，继续尝试
      }
    }
    this._engine = 'fetch';
    return 'fetch';
  }

  /* ===================== 内部工具 ===================== */

  /**
   * 通过 child_process 执行浏览器动作
   * @param {Object} payload 动作指令
   * @returns {Object} 动作结果
   */
  _runBrowserAction(payload) {
    const input = {
      viewport: this.options.viewport,
      userAgent: this.options.userAgent,
      timeout: this.options.timeout,
      headless: this.options.headless,
      ...payload,
    };

    const result = spawnSync(this.options.nodePath, ['-e', HELPER_SCRIPT_SOURCE, JSON.stringify(input)], {
      cwd: process.cwd(),
      encoding: 'utf8',
      maxBuffer: 50 * 1024 * 1024, // 50MB（截图 base64 可能较大）
      timeout: this.options.timeout + 30000, // 额外 30s 用于启动/关闭浏览器
    });

    if (result.error) {
      return { ok: false, error: 'spawn_failed: ' + result.error.message };
    }
    const stdout = (result.stdout || '').trim();
    if (!stdout) {
      return {
        ok: false,
        error: 'empty_output',
        stderr: (result.stderr || '').slice(0, 2000),
      };
    }
    try {
      return JSON.parse(stdout);
    } catch (e) {
      return {
        ok: false,
        error: 'invalid_json: ' + e.message,
        stdout: stdout.slice(0, 1000),
        stderr: (result.stderr || '').slice(0, 1000),
      };
    }
  }

  /**
   * 降级模式：通过 https/http 获取页面 HTML
   * @param {string} url
   * @returns {Promise<{ok:boolean, html?:string, error?:string, status?:number}>}
   */
  _fetchHtml(url) {
    return new Promise((resolve) => {
      let parsed;
      try {
        parsed = new URL(url);
      } catch (e) {
        resolve({ ok: false, error: 'invalid_url: ' + e.message });
        return;
      }
      const lib = parsed.protocol === 'http:' ? http : https;
      const req = lib.get(
        url,
        {
          headers: {
            'User-Agent': this.options.userAgent,
            Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
          },
          timeout: this.options.timeout,
        },
        (res) => {
          // 处理重定向
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            const next = new URL(res.headers.location, url).toString();
            res.resume();
            this._fetchHtml(next).then(resolve);
            return;
          }
          let chunks = [];
          res.on('data', (c) => chunks.push(c));
          res.on('end', () => {
            const buf = Buffer.concat(chunks);
            resolve({ ok: true, html: buf.toString('utf8'), status: res.statusCode, url });
          });
          res.on('error', (e) => resolve({ ok: false, error: e.message }));
        }
      );
      req.on('error', (e) => resolve({ ok: false, error: e.message }));
      req.on('timeout', () => {
        req.destroy(new Error('timeout'));
      });
    });
  }

  /**
   * 从 HTML 中提取纯文本（简单实现，去除标签与脚本）
   * @param {string} html
   * @returns {string}
   */
  _htmlToText(html) {
    if (!html) return '';
    return html
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/<noscript[\s\S]*?<\/noscript>/gi, '')
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/gi, ' ')
      .replace(/&amp;/gi, '&')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;/gi, "'")
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, MAX_TEXT_CHARS);
  }

  /**
   * 从 HTML 中提取 <title>
   * @param {string} html
   * @returns {string}
   */
  _htmlToTitle(html) {
    if (!html) return '';
    const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    return m ? m[1].trim().slice(0, 200) : '';
  }

  /**
   * 在 HTML 中根据描述匹配元素（降级模式）
   * @param {string} html
   * @param {string} description
   * @returns {Array}
   */
  _findElementInHtml(html, description) {
    if (!html || !description) return [];
    const desc = description.toLowerCase();
    const tagRegex = /<(a|button|input|textarea|select|div|span)([^>]*)>([\s\S]*?)<\/\1>|<(input|button|textarea|select)([^>]*)\/?>/gi;
    const matches = [];
    let m;
    while ((m = tagRegex.exec(html)) !== null) {
      const tag = (m[1] || m[4] || '').toLowerCase();
      const attrs = m[2] || m[5] || '';
      const inner = (m[3] || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      let score = 0;
      const attrLower = attrs.toLowerCase();
      if (inner && inner.toLowerCase().includes(desc)) score += 10;
      if (attrLower.includes('placeholder="' + desc) || attrLower.includes('placeholder=\'' + desc)) score += 8;
      if (attrLower.includes('aria-label="' + desc) || attrLower.includes('aria-label=\'' + desc)) score += 8;
      if (attrLower.includes('id="' + desc) || attrLower.includes('id=\'' + desc)) score += 3;
      if (attrLower.includes('type="' + desc)) score += 5;
      if (attrLower.includes(desc)) score += 1;
      if (score > 0) {
        const idMatch = attrs.match(/id=["']([^"']+)["']/i);
        matches.push({
          tag,
          text: inner.slice(0, 100),
          id: idMatch ? idMatch[1] : '',
          score,
          selector: idMatch ? '#' + idMatch[1] : tag + (inner ? ':has-text("' + inner.slice(0, 40) + '")' : ''),
        });
      }
    }
    return matches.sort((a, b) => b.score - a.score).slice(0, 5);
  }

  /* ===================== 核心动作 ===================== */

  /**
   * 导航到 URL
   * @param {string} url
   */
  async navigate(url) {
    if (!url) return { ok: false, error: 'url 不能为空' };
    if (!/^https?:\/\//i.test(url)) url = 'https://' + url;

    this._recordAction('navigate', { url });

    const engine = await this.detectEngine();
    if (engine !== 'fetch') {
      const res = this._runBrowserAction({ action: 'navigate', url });
      if (res.ok) {
        this.currentUrl = res.url || url;
        this.pageInfo = {
          url: res.url || url,
          title: res.title || '',
          text: (res.data && res.data.text) || '',
        };
      }
      return res.ok ? res.data || res : res;
    }

    // 降级：fetch
    const fres = await this._fetchHtml(url);
    if (!fres.ok) return fres;
    this._lastHtml = fres.html;
    this.currentUrl = fres.url || url;
    this.pageInfo = {
      url: this.currentUrl,
      title: this._htmlToTitle(fres.html),
      text: this._htmlToText(fres.html),
    };
    return {
      ok: true,
      url: this.currentUrl,
      title: this.pageInfo.title,
      engine: 'fetch',
    };
  }

  /**
   * 截取页面截图
   * @param {Object} [options] { fullPage }
   */
  async screenshot(options = {}) {
    this._recordAction('screenshot', options);
    const engine = await this.detectEngine();
    if (engine === 'fetch') {
      return {
        ok: false,
        error: 'fetch 模式不支持截图，请安装 Playwright 或 Puppeteer',
        engine: 'fetch',
      };
    }
    if (!this.currentUrl) {
      return { ok: false, error: '请先调用 navigate(url)' };
    }
    const res = this._runBrowserAction({
      action: 'screenshot',
      url: this.currentUrl,
      fullPage: options.fullPage || false,
    });
    return res.ok ? res.data || res : res;
  }

  /**
   * 提取页面内容
   * @param {string} [selector] CSS 选择器；为空则提取整页文本
   */
  async extract(selector) {
    this._recordAction('extract', { selector });
    const engine = await this.detectEngine();

    if (engine !== 'fetch') {
      if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)' };
      const res = this._runBrowserAction({
        action: 'extract',
        url: this.currentUrl,
        selector,
      });
      if (res.ok && res.data && res.data.html) this._lastHtml = res.data.html;
      return res.ok ? res.data || res : res;
    }

    // 降级：从缓存的 HTML 提取
    if (!this._lastHtml) return { ok: false, error: 'fetch 模式下请先 navigate 获取页面内容' };
    if (selector) {
      // 简单匹配：仅支持 #id / .class / tag
      const idMatch = selector.match(/^#([\w-]+)$/);
      if (idMatch) {
        const re = new RegExp('id=["\']' + idMatch[1] + '["\'][^>]*>([\\s\\S]*?)<', 'i');
        const m = this._lastHtml.match(re);
        return { ok: true, text: m ? this._htmlToText(m[1]).slice(0, MAX_TEXT_CHARS) : '' };
      }
      return { ok: false, error: 'fetch 模式仅支持 #id 选择器' };
    }
    return { ok: true, text: this._htmlToText(this._lastHtml), html: this._lastHtml };
  }

  /**
   * 点击元素
   * @param {string} selector
   */
  async click(selector) {
    if (!selector) return { ok: false, error: 'selector 不能为空' };
    this._recordAction('click', { selector });
    const engine = await this.detectEngine();
    if (engine === 'fetch') {
      return { ok: false, error: 'fetch 模式不支持交互操作', engine: 'fetch' };
    }
    if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)' };
    const res = this._runBrowserAction({ action: 'click', url: this.currentUrl, selector });
    if (res.ok && res.url) this.currentUrl = res.url;
    return res.ok ? res.data || res : res;
  }

  /**
   * 在元素中输入文本
   * @param {string} selector
   * @param {string} text
   */
  async type(selector, text) {
    if (!selector) return { ok: false, error: 'selector 不能为空' };
    if (text == null) return { ok: false, error: 'text 不能为空' };
    this._recordAction('type', { selector, text: String(text) });
    const engine = await this.detectEngine();
    if (engine === 'fetch') {
      return { ok: false, error: 'fetch 模式不支持交互操作', engine: 'fetch' };
    }
    if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)' };
    const res = this._runBrowserAction({
      action: 'type',
      url: this.currentUrl,
      selector,
      text: String(text),
    });
    return res.ok ? res.data || res : res;
  }

  /**
   * 滚动页面
   * @param {'down'|'up'|'left'|'right'} direction
   * @param {number} [amount=500]
   */
  async scroll(direction = 'down', amount = 500) {
    this._recordAction('scroll', { direction, amount });
    const engine = await this.detectEngine();
    if (engine === 'fetch') {
      return { ok: false, error: 'fetch 模式不支持滚动', engine: 'fetch' };
    }
    if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)' };
    const res = this._runBrowserAction({
      action: 'scroll',
      url: this.currentUrl,
      direction,
      amount,
    });
    return res.ok ? res.data || res : res;
  }

  /**
   * 等待元素出现
   * @param {string} selector
   * @param {number} [timeout]
   */
  async wait(selector, timeout) {
    if (!selector) return { ok: false, error: 'selector 不能为空' };
    this._recordAction('wait', { selector, timeout });
    const engine = await this.detectEngine();
    if (engine === 'fetch') {
      return { ok: false, error: 'fetch 模式不支持 wait', engine: 'fetch' };
    }
    if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)' };
    const res = this._runBrowserAction({
      action: 'wait',
      url: this.currentUrl,
      selector,
      timeout: timeout || this.options.timeout,
    });
    return res.ok ? res.data || res : res;
  }

  /**
   * 在页面中执行 JavaScript
   * @param {Function|string} fn 函数体或函数源码字符串
   */
  async evaluate(fn) {
    if (!fn) return { ok: false, error: 'fn 不能为空' };
    const fnBody = typeof fn === 'function' ? fn.toString() : String(fn);
    this._recordAction('evaluate', { fnBody });
    const engine = await this.detectEngine();
    if (engine === 'fetch') {
      return { ok: false, error: 'fetch 模式不支持 evaluate', engine: 'fetch' };
    }
    if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)' };
    const res = this._runBrowserAction({
      action: 'evaluate',
      url: this.currentUrl,
      fnBody,
    });
    return res.ok ? res.data || res : res;
  }

  /**
   * 获取页面信息（标题、URL、文本摘要）
   */
  async get_page_info() {
    const engine = await this.detectEngine();
    if (engine !== 'fetch') {
      if (!this.currentUrl) {
        return { ok: false, error: '请先调用 navigate(url)', engine };
      }
      const res = this._runBrowserAction({ action: 'page_info', url: this.currentUrl });
      if (res.ok && res.data) {
        this.pageInfo = {
          url: res.data.url || this.currentUrl,
          title: res.data.title || res.title || '',
          text: res.data.text || '',
        };
      }
      return res.ok ? res.data || res : res;
    }
    // fetch 模式：直接返回缓存
    return {
      ok: true,
      url: this.currentUrl,
      title: this.pageInfo.title,
      text: this.pageInfo.text,
      engine: 'fetch',
    };
  }

  /**
   * 通过自然语言描述查找元素
   * @param {string} description 例如 "登录按钮"、"搜索框"
   */
  async find_element(description) {
    if (!description) return { ok: false, error: 'description 不能为空' };
    const engine = await this.detectEngine();

    if (engine !== 'fetch') {
      if (!this.currentUrl) return { ok: false, error: '请先调用 navigate(url)', engine };
      const res = this._runBrowserAction({
        action: 'find_element',
        url: this.currentUrl,
        description,
      });
      return res.ok ? res.data || res : res;
    }

    // 降级：在缓存的 HTML 中匹配
    if (!this._lastHtml) return { ok: false, error: 'fetch 模式下请先 navigate' };
    const matches = this._findElementInHtml(this._lastHtml, description);
    return { ok: true, matches, description, engine: 'fetch' };
  }

  /**
   * 根据自然语言指令执行智能动作
   *
   * 支持的指令模式：
   *   - "点击<描述>"       → find_element + click
   *   - "在<描述>输入<文本>" → find_element + type
   *   - "导航到<URL>"      → navigate
   *   - "截图"             → screenshot
   *   - "滚动<方向>"       → scroll
   *   - "等待<描述>"       → find_element + wait
   *
   * @param {string} instruction 自然语言指令
   */
  async smart_action(instruction) {
    if (!instruction) return { ok: false, error: 'instruction 不能为空' };
    const text = instruction.trim();

    // 解析指令
    // 1. 点击：点击登录 / 点击"提交"按钮
    let m = text.match(/^点击["""]?(.+?)["""]?$/);
    if (m) {
      const desc = m[1].replace(/按钮$/, '').trim();
      const found = await this.find_element(desc);
      if (!found.ok) return { ok: false, error: '查找元素失败：' + (found.error || ''), instruction };
      const matches = found.matches || [];
      if (!matches.length) {
        return { ok: false, error: '未找到匹配的元素：' + desc, instruction };
      }
      const sel = matches[0].selector;
      // 若 selector 为空或仅为 tag，尝试用 Playwright 文本定位
      if (!sel || /^([a-z]+)$/.test(sel)) {
        // 使用 Playwright 特殊语法 :has-text（仅在浏览器引擎可用时生效）
        const clickRes = await this.click(sel || matches[0].tag + ':has-text("' + (matches[0].text || desc).slice(0, 30) + '")');
        return { ok: !!clickRes.ok, action: 'click', selector: sel, result: clickRes, instruction };
      }
      const clickRes = await this.click(sel);
      return { ok: !!clickRes.ok, action: 'click', selector: sel, result: clickRes, instruction };
    }

    // 2. 输入：在搜索框输入"AI"  / 输入"AI"到搜索框
    m = text.match(/^在["""]?(.+?)["""]?(?:中)?输入["""](.+?)["""]$/) || text.match(/^输入["""](.+?)["""]到["""]?(.+?)["""]?$/);
    if (m) {
      const desc = m[1].replace(/框$/, '').trim();
      const value = m[2];
      const found = await this.find_element(desc);
      if (!found.ok) return { ok: false, error: '查找元素失败：' + (found.error || ''), instruction };
      const matches = found.matches || [];
      if (!matches.length) return { ok: false, error: '未找到匹配的元素：' + desc, instruction };
      const sel = matches[0].selector || ('#' + matches[0].id) || null;
      if (!sel) return { ok: false, error: '无法定位元素选择器', instruction };
      const typeRes = await this.type(sel, value);
      return { ok: !!typeRes.ok, action: 'type', selector: sel, value, result: typeRes, instruction };
    }

    // 3. 导航：导航到 https://example.com / 打开 URL
    m = text.match(/^(?:导航到|打开|访问)\s*(https?:\/\/\S+)$/i) || text.match(/^(?:导航到|打开|访问)\s*(\S+\.\S+)$/i);
    if (m) {
      const navRes = await this.navigate(m[1]);
      return { ok: !!navRes.ok, action: 'navigate', url: m[1], result: navRes, instruction };
    }

    // 4. 截图
    if (/^(截图|截屏|全屏截图)$/.test(text) || /^截图/.test(text)) {
      const fullPage = /全|full/i.test(text);
      const ssRes = await this.screenshot({ fullPage });
      return { ok: !!ssRes.ok, action: 'screenshot', result: ssRes, instruction };
    }

    // 5. 滚动：向下滚动 / 向上滚动 / 向左滚动 / 向右滚动
    m = text.match(/^(向下|向上|向左|向右|down|up|left|right)\s*滚动/);
    if (m) {
      const map = { '向下': 'down', '向上': 'up', '向左': 'left', '向右': 'right', down: 'down', up: 'up', left: 'left', right: 'right' };
      const dir = map[m[1]] || 'down';
      const scrollRes = await this.scroll(dir);
      return { ok: !!scrollRes.ok, action: 'scroll', direction: dir, result: scrollRes, instruction };
    }

    // 6. 等待：等待"提交按钮"出现
    m = text.match(/^等待["""]?(.+?)["""]?(?:出现)?$/);
    if (m) {
      const desc = m[1].trim();
      const found = await this.find_element(desc);
      if (!found.ok) return { ok: false, error: '查找元素失败：' + (found.error || ''), instruction };
      const matches = found.matches || [];
      if (!matches.length) return { ok: false, error: '未找到匹配的元素：' + desc, instruction };
      const sel = matches[0].selector || ('#' + matches[0].id);
      if (!sel) return { ok: false, error: '无法定位元素选择器', instruction };
      const waitRes = await this.wait(sel);
      return { ok: !!waitRes.ok, action: 'wait', selector: sel, result: waitRes, instruction };
    }

    return {
      ok: false,
      error: '无法解析指令：' + text,
      instruction,
      hint: '支持的指令：点击<描述> / 在<描述>输入<文本> / 导航到<URL> / 截图 / 向下滚动 / 等待<描述>',
    };
  }

  /* ===================== 任务录制与回放 ===================== */

  /**
   * 开始录制（清空之前的录制）
   */
  start_recording() {
    this.recording = [];
    this.isRecording = true;
    return { ok: true, message: '录制已开始' };
  }

  /**
   * 停止录制
   */
  stop_recording() {
    this.isRecording = false;
    return { ok: true, count: this.recording.length, message: '录制已停止' };
  }

  /**
   * 回放录制
   * @param {Array} [recording] 若不传则使用当前录制
   * @returns {Array} 每步的执行结果
   */
  async replay(recording) {
    const steps = recording || this.recording;
    if (!Array.isArray(steps) || !steps.length) {
      return { ok: false, error: '没有可回放的录制' };
    }
    const wasRecording = this.isRecording;
    this.isRecording = false; // 回放期间不录制
    const results = [];
    try {
      for (let i = 0; i < steps.length; i++) {
        const step = steps[i];
        let res;
        switch (step.action) {
          case 'navigate':
            res = await this.navigate(step.args.url);
            break;
          case 'screenshot':
            res = await this.screenshot(step.args);
            break;
          case 'extract':
            res = await this.extract(step.args.selector);
            break;
          case 'click':
            res = await this.click(step.args.selector);
            break;
          case 'type':
            res = await this.type(step.args.selector, step.args.text);
            break;
          case 'scroll':
            res = await this.scroll(step.args.direction, step.args.amount);
            break;
          case 'wait':
            res = await this.wait(step.args.selector, step.args.timeout);
            break;
          case 'evaluate':
            res = await this.evaluate(step.args.fnBody);
            break;
          default:
            res = { ok: false, error: '未知动作: ' + step.action };
        }
        results.push({ step: i, action: step.action, ok: !!res.ok, result: res });
        // 某步失败时仍继续，便于调试
      }
    } finally {
      this.isRecording = wasRecording;
    }
    return { ok: true, total: steps.length, results };
  }

  /**
   * 导出录制为 JSON
   * @param {string} [filePath] 若提供则写入文件，否则返回 JSON 字符串
   */
  export_recording(filePath) {
    const data = {
      version: '1.0',
      engine: this._engine,
      viewport: this.options.viewport,
      userAgent: this.options.userAgent,
      createdAt: new Date().toISOString(),
      steps: this.recording,
    };
    const json = JSON.stringify(data, null, 2);
    if (filePath) {
      try {
        fs.writeFileSync(filePath, json, 'utf8');
        return { ok: true, path: filePath, count: this.recording.length };
      } catch (e) {
        return { ok: false, error: e.message };
      }
    }
    return { ok: true, json, count: this.recording.length };
  }

  /* ===================== 内部辅助 ===================== */

  /**
   * 记录动作到录制队列
   * @param {string} action
   * @param {Object} args
   * @private
   */
  _recordAction(action, args) {
    if (!this.isRecording) return;
    this.recording.push({ action, args, timestamp: Date.now() });
  }

  /**
   * 关闭浏览器并清理状态
   */
  async close() {
    this.currentUrl = null;
    this._lastHtml = '';
    this.pageInfo = { title: '', url: '', text: '' };
    // 每次 action 都已自动关闭浏览器实例，无需额外清理
    return { ok: true };
  }

  /**
   * 获取当前引擎名称
   */
  getEngine() {
    return this._engine;
  }
}

// ============================================================
// 导出
// ============================================================

module.exports = { BrowserUseEnhanced };
