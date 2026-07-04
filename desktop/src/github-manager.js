/**
 * GitHub API 集成管理器
 * ------------------------------
 * 功能说明：
 *   1. 仓库管理：列出仓库、查看仓库详情、创建仓库
 *   2. Issue 管理：列出 Issues、创建 Issue、查看 Issue 详情
 *   3. PR 管理：列出 Pull Requests、创建 PR、查看 PR 详情、合并 PR
 *   4. 分支管理：列出分支、创建分支
 *   5. Actions / CI：列出 Workflow runs、查看运行详情
 *   6. 代码搜索：搜索代码、搜索仓库
 *   7. 用户信息：获取认证用户信息、查看贡献
 *
 * 实现说明：
 *   - 仅使用 Node.js 内置的 https 模块，不依赖任何第三方库
 *   - 采用 GitHub REST API v3
 *   - 支持 Personal Access Token (PAT) 认证方式
 *   - 统一封装请求、分页与错误处理逻辑
 */

'use strict';

const https = require('https');
const { URL } = require('url');

class GitHubManager {
  /**
   * 构造函数
   * @param {Object} options 配置项
   * @param {string} options.token Personal Access Token (PAT)
   * @param {string} [options.baseUrl] API 基础 URL，默认 https://api.github.com
   * @param {number} [options.timeout] 请求超时时间(毫秒)，默认 30000
   * @param {string} [options.userAgent] User-Agent 标识
   */
  constructor(options = {}) {
    if (!options.token) {
      throw new Error('GitHubManager 需要 Personal Access Token (token)');
    }
    this.token = options.token;
    this.baseUrl = (options.baseUrl || 'https://api.github.com').replace(/\/$/, '');
    this.timeout = options.timeout || 30000;
    this.userAgent = options.userAgent || 'YNEX-Desktop-GitHubManager/1.0';
  }

  /* ===================== 内部工具方法 ===================== */

  /**
   * 构造请求头
   * @private
   */
  _buildHeaders(extra = {}) {
    return Object.assign(
      {
        'User-Agent': this.userAgent,
        Authorization: `Bearer ${this.token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      extra
    );
  }

  /**
   * 将对象序列化为 query string
   * @private
   */
  _stringifyQuery(params = {}) {
    const keys = Object.keys(params).filter(
      (k) => params[k] !== undefined && params[k] !== null && params[k] !== ''
    );
    if (keys.length === 0) return '';
    const usp = new URLSearchParams();
    for (const k of keys) {
      usp.set(k, params[k]);
    }
    return `?${usp.toString()}`;
  }

  /**
   * 发起 HTTPS 请求(基于内置 https 模块)
   * @param {string} method HTTP 方法
   * @param {string} path 接口路径(可包含 query)
   * @param {Object} [body] 请求体
   * @returns {Promise<Object>} { status, headers, data }
   * @private
   */
  _request(method, path, body) {
    return new Promise((resolve, reject) => {
      const fullUrl = path.startsWith('http') ? path : `${this.baseUrl}${path}`;
      const parsed = new URL(fullUrl);
      const isGetHead = method === 'GET' || method === 'HEAD';
      let payload = null;

      const headers = this._buildHeaders();
      if (!isGetHead && body !== undefined && body !== null) {
        payload = JSON.stringify(body);
        headers['Content-Type'] = 'application/json';
        headers['Content-Length'] = Buffer.byteLength(payload);
      }

      const options = {
        method,
        hostname: parsed.hostname,
        port: parsed.port || 443,
        path: `${parsed.pathname}${parsed.search}`,
        headers,
        timeout: this.timeout
      };

      const req = https.request(options, (res) => {
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => {
          const buf = Buffer.concat(chunks);
          const text = buf.toString('utf8');
          let data = null;
          if (text) {
            try {
              data = JSON.parse(text);
            } catch (_) {
              data = text;
            }
          }
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve({ status: res.statusCode, headers: res.headers, data });
          } else {
            const message =
              (data && (data.message || data.error)) ||
              `GitHub API 请求失败: HTTP ${res.statusCode}`;
            const err = new Error(message);
            err.status = res.statusCode;
            err.headers = res.headers;
            err.body = data;
            reject(err);
          }
        });
      });

      req.on('timeout', () => {
        req.destroy(new Error(`GitHub API 请求超时(${this.timeout}ms)`));
      });
      req.on('error', reject);

      if (payload) req.write(payload);
      req.end();
    });
  }

  /**
   * 解析分页参数
   * @private
   */
  _normalizePaging(page, perPage) {
    return {
      page: Math.max(1, parseInt(page, 10) || 1),
      per_page: Math.min(100, Math.max(1, parseInt(perPage, 10) || 30))
    };
  }

  /* ===================== 仓库管理 ===================== */

  /**
   * 列出当前认证用户的仓库
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   * @param {string} [options.sort] 排序字段 created/updated/pushed/full_name
   * @param {string} [options.direction] asc/desc
   * @param {string} [options.visibility] all/public/private
   */
  async listRepositories(options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      page,
      per_page,
      sort: options.sort,
      direction: options.direction,
      visibility: options.visibility
    });
    const res = await this._request('GET', `/user/repos${query}`);
    return res.data;
  }

  /**
   * 列出指定用户/组织的仓库
   * @param {string} owner 用户名或组织名
   * @param {Object} [options] 同 listRepositories
   */
  async listUserRepositories(owner, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      page,
      per_page,
      sort: options.sort,
      direction: options.direction,
      type: options.type
    });
    const res = await this._request('GET', `/users/${owner}/repos${query}`);
    return res.data;
  }

  /**
   * 查看仓库详情
   * @param {string} owner 仓库所有者
   * @param {string} repo 仓库名
   */
  async getRepository(owner, repo) {
    const res = await this._request('GET', `/repos/${owner}/${repo}`);
    return res.data;
  }

  /**
   * 创建仓库
   * @param {string} name 仓库名
   * @param {Object} [options]
   * @param {string} [options.description] 描述
   * @param {boolean} [options.private=false] 是否私有
   * @param {boolean} [options.auto_init=true] 是否自动初始化 README
   * @param {string} [options.org] 若指定则在对应组织下创建仓库
   * @param {string} [options.gitignore_template] .gitignore 模板
   * @param {string} [options.license_template] license 模板
   */
  async createRepository(name, options = {}) {
    const body = {
      name,
      description: options.description,
      private: options.private === undefined ? true : !!options.private, // 默认创建私有仓库，保护项目不开源
      auto_init: options.auto_init === undefined ? true : !!options.auto_init,
      gitignore_template: options.gitignore_template,
      license_template: options.license_template
    };
    const path = options.org ? `/orgs/${options.org}/repos` : '/user/repos';
    const res = await this._request('POST', path, body);
    return res.data;
  }

  /* ===================== Issue 管理 ===================== */

  /**
   * 列出仓库 Issues
   * @param {string} owner
   * @param {string} repo
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   * @param {string} [options.state] open/closed/all
   * @param {string} [options.labels] 逗号分隔的标签
   * @param {string} [options.sort] created/updated/comments
   * @param {string} [options.direction] asc/desc
   * @param {string} [options.since] ISO8601 时间戳，仅返回此时间之后更新的 issue
   */
  async listIssues(owner, repo, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      page,
      per_page,
      state: options.state || 'open',
      labels: options.labels,
      sort: options.sort,
      direction: options.direction,
      since: options.since
    });
    const res = await this._request('GET', `/repos/${owner}/${repo}/issues${query}`);
    return res.data;
  }

  /**
   * 查看 Issue 详情
   * @param {string} owner
   * @param {string} repo
   * @param {number} issueNumber
   */
  async getIssue(owner, repo, issueNumber) {
    const res = await this._request('GET', `/repos/${owner}/${repo}/issues/${issueNumber}`);
    return res.data;
  }

  /**
   * 创建 Issue
   * @param {string} owner
   * @param {string} repo
   * @param {Object} payload
   * @param {string} payload.title 标题
   * @param {string} [payload.body] 内容
   * @param {string[]} [payload.labels] 标签数组
   * @param {string[]} [payload.assignees] 指派人
   * @param {number} [payload.milestone] milestone 编号
   */
  async createIssue(owner, repo, payload) {
    if (!payload || !payload.title) {
      throw new Error('createIssue: payload.title 必填');
    }
    const res = await this._request('POST', `/repos/${owner}/${repo}/issues`, payload);
    return res.data;
  }

  /* ===================== PR 管理 ===================== */

  /**
   * 列出 Pull Requests
   * @param {string} owner
   * @param {string} repo
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   * @param {string} [options.state] open/closed/all
   * @param {string} [options.head] 过滤来源分支 (如 user:ref-name)
   * @param {string} [options.base] 过滤目标分支
   * @param {string} [options.sort] created/updated/popularity/long-running
   * @param {string} [options.direction] asc/desc
   */
  async listPullRequests(owner, repo, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      page,
      per_page,
      state: options.state || 'open',
      head: options.head,
      base: options.base,
      sort: options.sort,
      direction: options.direction
    });
    const res = await this._request('GET', `/repos/${owner}/${repo}/pulls${query}`);
    return res.data;
  }

  /**
   * 查看 PR 详情
   * @param {string} owner
   * @param {string} repo
   * @param {number} prNumber
   */
  async getPullRequest(owner, repo, prNumber) {
    const res = await this._request('GET', `/repos/${owner}/${repo}/pulls/${prNumber}`);
    return res.data;
  }

  /**
   * 创建 Pull Request
   * @param {string} owner
   * @param {string} repo
   * @param {Object} payload
   * @param {string} payload.title 标题
   * @param {string} payload.head 源分支 (head:ref 或 user:ref)
   * @param {string} payload.base 目标分支
   * @param {string} [payload.body] 描述
   * @param {boolean} [payload.draft] 是否为草稿
   * @param {boolean} [payload.maintainer_can_modify] 维护者是否可修改
   */
  async createPullRequest(owner, repo, payload) {
    if (!payload || !payload.title || !payload.head || !payload.base) {
      throw new Error('createPullRequest: payload.title / head / base 均为必填');
    }
    const res = await this._request('POST', `/repos/${owner}/${repo}/pulls`, payload);
    return res.data;
  }

  /**
   * 合并 Pull Request
   * @param {string} owner
   * @param {string} repo
   * @param {number} prNumber
   * @param {Object} [options]
   * @param {string} [options.commit_title] 合并提交标题
   * @param {string} [options.commit_message] 合并提交描述
   * @param {string} [options.merge_method] merge/squash/rebase，默认 merge
   * @param {string} [options.sha] 期望合并到的 commit SHA(校验)
   */
  async mergePullRequest(owner, repo, prNumber, options = {}) {
    const body = {
      commit_title: options.commit_title,
      commit_message: options.commit_message,
      merge_method: options.merge_method || 'merge',
      sha: options.sha
    };
    const res = await this._request(
      'PUT',
      `/repos/${owner}/${repo}/pulls/${prNumber}/merge`,
      body
    );
    return res.data;
  }

  /* ===================== 分支管理 ===================== */

  /**
   * 列出仓库分支
   * @param {string} owner
   * @param {string} repo
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   * @param {boolean} [options.protected] 仅返回受保护分支
   */
  async listBranches(owner, repo, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      page,
      per_page,
      protected: options.protected
    });
    const res = await this._request('GET', `/repos/${owner}/${repo}/branches${query}`);
    return res.data;
  }

  /**
   * 获取分支信息
   * @param {string} owner
   * @param {string} repo
   * @param {string} branch 分支名
   */
  async getBranch(owner, repo, branch) {
    const res = await this._request('GET', `/repos/${owner}/${repo}/branches/${branch}`);
    return res.data;
  }

  /**
   * 创建分支(基于指定 ref 创建)
   * @param {string} owner
   * @param {string} repo
   * @param {Object} payload
   * @param {string} payload.ref 新分支名 (如 refs/heads/feature-x)
   * @param {string} payload.sha 起始 commit SHA
   */
  async createBranch(owner, repo, payload) {
    if (!payload || !payload.ref || !payload.sha) {
      throw new Error('createBranch: payload.ref / payload.sha 必填');
    }
    const res = await this._request('POST', `/repos/${owner}/${repo}/git/refs`, payload);
    return res.data;
  }

  /* ===================== Actions / CI ===================== */

  /**
   * 列出 Workflow runs
   * @param {string} owner
   * @param {string} repo
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {options.per_page} [options.per_page=30]
   * @param {string} [options.actor] 触发者登录名
   * @param {string} [options.branch] 按分支过滤
   * @param {string} [options.event] 触发事件类型 (如 push, pull_request)
   * @param {string} [options.status] 状态 (queued/in_progress/completed 等)
   */
  async listWorkflowRuns(owner, repo, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      page,
      per_page,
      actor: options.actor,
      branch: options.branch,
      event: options.event,
      status: options.status
    });
    const res = await this._request(
      'GET',
      `/repos/${owner}/${repo}/actions/runs${query}`
    );
    return res.data;
  }

  /**
   * 查看 Workflow run 详情
   * @param {string} owner
   * @param {string} repo
   * @param {number} runId
   */
  async getWorkflowRun(owner, repo, runId) {
    const res = await this._request(
      'GET',
      `/repos/${owner}/${repo}/actions/runs/${runId}`
    );
    return res.data;
  }

  /**
   * 列出仓库中的 Workflows
   * @param {string} owner
   * @param {string} repo
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   */
  async listWorkflows(owner, repo, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({ page, per_page });
    const res = await this._request(
      'GET',
      `/repos/${owner}/${repo}/actions/workflows${query}`
    );
    return res.data;
  }

  /**
   * 获取一次 Workflow run 的日志下载地址
   * @param {string} owner
   * @param {string} repo
   * @param {number} runId
   */
  async getWorkflowRunLogsUrl(owner, repo, runId) {
    const res = await this._request(
      'GET',
      `/repos/${owner}/${repo}/actions/runs/${runId}/logs`
    );
    return { url: res.headers && res.headers.location };
  }

  /* ===================== 代码搜索 ===================== */

  /**
   * 搜索代码
   * @param {string} q 搜索语句 (GitHub Search 语法)
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   * @param {string} [options.sort] indexed
   * @param {string} [options.order] asc/desc
   */
  async searchCode(q, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      q,
      page,
      per_page,
      sort: options.sort,
      order: options.order
    });
    const res = await this._request('GET', `/search/code${query}`);
    return res.data;
  }

  /**
   * 搜索仓库
   * @param {string} q 搜索语句
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   * @param {string} [options.sort] stars/forks/help-wanted-issues/updated
   * @param {string} [options.order] asc/desc
   */
  async searchRepositories(q, options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({
      q,
      page,
      per_page,
      sort: options.sort,
      order: options.order
    });
    const res = await this._request('GET', `/search/repositories${query}`);
    return res.data;
  }

  /* ===================== 用户信息 ===================== */

  /**
   * 获取当前认证用户信息
   */
  async getAuthenticatedUser() {
    const res = await this._request('GET', '/user');
    return res.data;
  }

  /**
   * 获取指定用户公开信息
   * @param {string} username 用户名
   */
  async getUser(username) {
    const res = await this._request('GET', `/users/${username}`);
    return res.data;
  }

  /**
   * 查看认证用户的贡献事件
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   */
  async listAuthenticatedUserEvents(options = {}) {
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({ page, per_page });
    const res = await this._request('GET', `/users/${await this._getAuthenticatedLogin()}/events${query}`);
    return res.data;
  }

  /**
   * 查看指定用户的事件(包含贡献信息)
   * @param {string} username
   * @param {Object} [options]
   * @param {number} [options.page=1]
   * @param {number} [options.per_page=30]
   */
  async listUserEvents(username, options = {}) {
    if (!username) throw new Error('listUserEvents: username 必填');
    const { page, per_page } = this._normalizePaging(options.page, options.per_page);
    const query = this._stringifyQuery({ page, per_page });
    const res = await this._request('GET', `/users/${username}/events${query}`);
    return res.data;
  }

  /**
   * 内部方法：获取认证用户的 login(避免与 getAuthenticatedUser 重复请求时使用)
   * @private
   */
  async _getAuthenticatedLogin() {
    const user = await this.getAuthenticatedUser();
    return user.login;
  }
}

module.exports = GitHubManager;
module.exports.GitHubManager = GitHubManager;
