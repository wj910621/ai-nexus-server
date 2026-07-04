/**
 * Y·NEX Desktop — CI/CD 面板管理器
 * 检测项目 CI/CD 配置、运行流水线、查看状态
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// 安全辅助：校验标识符只含字母/数字/-/_/:/.，防止命令注入
function _isValidIdentifier(s) {
  return typeof s === 'string' && /^[A-Za-z0-9_.:-]+$/.test(s);
}

// 安全辅助：运行子进程，统一参数校验与 shell:false 防注入
function _safeSpawn(prog, args, opts = {}) {
  return new Promise((resolve) => {
    // 强制 shell:false，避免命令字符串被 shell 解释
    const child = spawn(prog, args, {
      cwd: opts.cwd,
      shell: false,
      windowsHide: true,
      env: opts.env,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', d => stdout += d.toString());
    child.stderr.on('data', d => stderr += d.toString());
    child.on('close', (code) => resolve({ ok: code === 0, code, stdout, stderr }));
    child.on('error', (e) => resolve({ ok: false, error: e.message }));
  });
}

class CicdManager {
  constructor() {
    this.pipelines = new Map();
  }

  /**
   * 检测项目 CI/CD 配置
   */
  detectConfig(workspacePath) {
    const configs = [];
    const detectors = [
      { file: '.github/workflows', type: 'GitHub Actions', icon: '🐙' },
      { file: '.gitlab-ci.yml', type: 'GitLab CI', icon: '🦊' },
      { file: 'Jenkinsfile', type: 'Jenkins', icon: '👨‍🔧' },
      { file: '.circleci/config.yml', type: 'CircleCI', icon: '⭕' },
      { file: '.drone.yml', type: 'Drone CI', icon: '🚁' },
      { file: 'azure-pipelines.yml', type: 'Azure Pipelines', icon: '☁️' },
      { file: 'bitbucket-pipelines.yml', type: 'Bitbucket', icon: '📦' },
      { file: 'Dockerfile', type: 'Docker Build', icon: '🐳' },
      { file: 'docker-compose.yml', type: 'Docker Compose', icon: '🐳' },
      { file: 'Makefile', type: 'Make', icon: '🔨' },
      { file: 'package.json', type: 'npm scripts', icon: '📦' },
      { file: 'pyproject.toml', type: 'Python', icon: '🐍' },
    ];

    for (const detector of detectors) {
      const fullPath = path.join(workspacePath, detector.file);
      if (fs.existsSync(fullPath)) {
        const isDir = fs.statSync(fullPath).isDirectory();
        if (isDir && detector.file === '.github/workflows') {
          try {
            const workflows = fs.readdirSync(fullPath).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));
            for (const wf of workflows) {
              configs.push({
                type: detector.type,
                icon: detector.icon,
                file: path.join(detector.file, wf),
                name: wf.replace(/\.(yml|yaml)$/, '')
              });
            }
          } catch (e) {}
        } else if (!isDir) {
          configs.push({
            type: detector.type,
            icon: detector.icon,
            file: detector.file,
            name: detector.file
          });
        }
      }
    }

    return { configs };
  }

  /**
   * 运行 npm scripts
   */
  async runNpmScript(workspacePath, script) {
    // 校验 script 名只含安全字符，防止 `script; rm -rf /` 注入
    if (!_isValidIdentifier(script)) {
      return { ok: false, error: '非法的 npm script 名称（仅允许字母数字 _ . : -）' };
    }
    return _safeSpawn('npm', ['run', script], { cwd: workspacePath });
  }

  /**
   * 运行 Make 目标
   */
  async runMake(workspacePath, target) {
    if (!_isValidIdentifier(target)) {
      return { ok: false, error: '非法的 make target 名称（仅允许字母数字 _ . : -）' };
    }
    return _safeSpawn('make', [target], { cwd: workspacePath });
  }

  /**
   * 运行自定义命令
   * 安全策略：禁止 shell:true，将命令解析为 argv 数组；
   * 禁止管道/重定向/命令分隔符（| ; & ` $ > <），仅允许单条命令 + 参数。
   */
  async runCommand(workspacePath, command) {
    if (typeof command !== 'string' || !command.trim()) {
      return { ok: false, error: '空命令' };
    }
    // 危险字符黑名单（shell 元字符）
    const dangerous = ['|', ';', '&', '`', '$', '>', '<', '\n', '\r', '\\'];
    for (const d of dangerous) {
      if (command.includes(d)) {
        return { ok: false, error: `命令被拒绝：包含危险字符 '${d}'。runCommand 仅允许单条命令 + 参数，禁止管道/重定向/命令分隔。` };
      }
    }
    // 按空格分割为 argv（不完美，但配合 shell:false 已消除主要注入风险）
    const parts = command.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) {
      return { ok: false, error: '空命令' };
    }
    const prog = parts[0];
    const args = parts.slice(1);
    return _safeSpawn(prog, args, { cwd: workspacePath });
  }

  /**
   * 运行 Docker 构建
   */
  async runDockerBuild(workspacePath, dockerfile = 'Dockerfile', tag = 'ynex-app') {
    // 校验 dockerfile 文件名与 tag 仅含安全字符
    if (!_isValidIdentifier(dockerfile)) {
      return { ok: false, error: '非法的 Dockerfile 名称' };
    }
    if (!_isValidIdentifier(tag)) {
      return { ok: false, error: '非法的镜像 tag 名称' };
    }
    return _safeSpawn('docker', ['build', '-f', dockerfile, '-t', tag, '.'], { cwd: workspacePath });
  }
}

module.exports = { CicdManager };