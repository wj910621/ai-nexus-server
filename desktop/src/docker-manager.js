/**
 * Y·NEX Desktop — Docker 容器集成管理器
 * 通过 docker CLI 管理容器、镜像、卷
 */

const { spawn } = require('child_process');

class DockerManager {
  constructor() {
    this.dockerAvailable = false;
  }

  async _exec(args, cwd) {
    // 安全策略：强制 shell:false，所有参数以数组形式传入，
    // 避免字符串拼接导致的命令注入。
    return new Promise((resolve) => {
      const child = spawn('docker', args, { cwd, shell: false, windowsHide: true });
      let stdout = '';
      let stderr = '';
      child.stdout.on('data', d => stdout += d.toString());
      child.stderr.on('data', d => stderr += d.toString());
      child.on('close', (code) => resolve({ code, stdout, stderr }));
      child.on('error', () => resolve({ code: -1, stdout: '', stderr: 'docker 未安装或不可用' }));
    });
  }

  async checkAvailability() {
    const r = await this._exec(['--version']);
    this.dockerAvailable = r.code === 0;
    return { available: this.dockerAvailable, version: r.stdout.trim() };
  }

  async listContainers() {
    const r = await this._exec(['ps', '-a', '--format', '{{.ID}}|{{.Image}}|{{.Names}}|{{.Status}}|{{.Ports}}']);
    if (r.code !== 0) return { error: r.stderr };
    const containers = r.stdout.trim().split('\n').filter(Boolean).map(line => {
      const [id, image, names, status, ports] = line.split('|');
      return { id, image, names, status, ports };
    });
    return { containers };
  }

  async listImages() {
    const r = await this._exec(['images', '--format', '{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}']);
    if (r.code !== 0) return { error: r.stderr };
    const images = r.stdout.trim().split('\n').filter(Boolean).map(line => {
      const [repo, tag, id, size] = line.split('|');
      return { repo, tag, id, size };
    });
    return { images };
  }

  async startContainer(nameOrId) {
    const r = await this._exec(['start', nameOrId]);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async stopContainer(nameOrId) {
    const r = await this._exec(['stop', nameOrId]);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async restartContainer(nameOrId) {
    const r = await this._exec(['restart', nameOrId]);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async removeContainer(nameOrId) {
    const r = await this._exec(['rm', '-f', nameOrId]);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async containerLogs(nameOrId, tail = 100) {
    const r = await this._exec(['logs', '--tail', String(tail), nameOrId]);
    return { ok: r.code === 0, logs: r.stdout, error: r.stderr };
  }

  async execInContainer(nameOrId, command) {
    const r = await this._exec(['exec', nameOrId, ...command.split(' ')]);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async pullImage(image) {
    const r = await this._exec(['pull', image]);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async composeUp(composeFile, cwd) {
    const r = await this._exec(['compose', '-f', composeFile, 'up', '-d'], cwd);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }

  async composeDown(composeFile, cwd) {
    const r = await this._exec(['compose', '-f', composeFile, 'down'], cwd);
    return { ok: r.code === 0, output: r.stdout, error: r.stderr };
  }
}

module.exports = { DockerManager };