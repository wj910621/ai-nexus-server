/**
 * Y·NEX Desktop — 实时性能监控面板
 * 追踪 FPS、内存、CPU、网络延迟、缓存命中率
 */

class PerfMonitor {
  constructor() {
    this.metrics = {
      fps: [],
      memory: [],
      cpu: [],
      latency: [],
      startTime: Date.now(),
    };
    this.maxSamples = 120; // 保留最近 120 个样本（2 分钟）

    // 自动采样
    this._sampleInterval = null;
    this._fpsCounter = 0;
    this._fpsTimer = 0;
    this._lastFrameTime = 0;
    this._enabled = false;
  }

  start() {
    if (this._enabled) return;
    this._enabled = true;
    this._sampleInterval = setInterval(() => this._sample(), 1000);
    this._startFpsTracking();
    this._startCpuTracking();
  }

  stop() {
    this._enabled = false;
    if (this._sampleInterval) clearInterval(this._sampleInterval);
    this._sampleInterval = null;
  }

  _sample() {
    const now = Date.now();

    // 内存
    const mem = process.memoryUsage();
    this._pushMetric('memory', {
      heapUsed: (mem.heapUsed / 1024 / 1024).toFixed(1),
      heapTotal: (mem.heapTotal / 1024 / 1024).toFixed(1),
      rss: (mem.rss / 1024 / 1024).toFixed(1),
      external: (mem.external / 1024 / 1024).toFixed(1),
      arrayBuffers: (mem.arrayBuffers / 1024 / 1024).toFixed(1),
    });

    // FPS
    this._pushMetric('fps', {
      fps: this._fpsCounter,
      time: now,
    });

    // 网络延迟（ping localhost）
    this._measureLatency();
  }

  _startFpsTracking() {
    this._fpsCounter = 0;
    this._fpsTimer = setInterval(() => {
      this._fpsCounter = 0;
    }, 1000);
  }

  _startCpuTracking() {
    let lastUsage = process.cpuUsage();
    setInterval(() => {
      const usage = process.cpuUsage();
      const userDiff = usage.user - lastUsage.user;
      const sysDiff = usage.system - lastUsage.system;
      const totalDiff = userDiff + sysDiff;
      const cpuPercent = (totalDiff / 10000).toFixed(1);
      this._pushMetric('cpu', { percent: cpuPercent, time: Date.now() });
      lastUsage = usage;
    }, 2000);
  }

  async _measureLatency() {
    const start = Date.now();
    try {
      await new Promise((resolve, reject) => {
        const req = require('http').get('http://127.0.0.1:7777/api/health', (res) => {
          res.on('data', () => {});
          res.on('end', resolve);
        });
        req.on('error', reject);
        req.setTimeout(2000, () => { req.destroy(); resolve(); });
      });
      this._pushMetric('latency', { ms: Date.now() - start, ok: true });
    } catch (e) {
      this._pushMetric('latency', { ms: -1, ok: false });
    }
  }

  _pushMetric(name, value) {
    this.metrics[name].push(value);
    if (this.metrics[name].length > this.maxSamples) {
      this.metrics[name].shift();
    }
  }

  /**
   * 获取性能快照
   */
  getSnapshot() {
    const avg = (arr, key) => {
      if (!arr.length) return 0;
      return (arr.reduce((s, v) => s + (parseFloat(v[key]) || 0), 0) / arr.length).toFixed(1);
    };

    const fpsArr = this.metrics.fps;
    const memArr = this.metrics.memory;
    const cpuArr = this.metrics.cpu;
    const latArr = this.metrics.latency.filter(l => l.ok);

    return {
      uptime: Math.floor((Date.now() - this.metrics.startTime) / 1000),
      fps: {
        current: fpsArr.length > 0 ? fpsArr[fpsArr.length - 1].fps : 0,
        avg: avg(fpsArr, 'fps'),
        min: fpsArr.length > 0 ? Math.min(...fpsArr.map(f => f.fps)) : 0,
        max: fpsArr.length > 0 ? Math.max(...fpsArr.map(f => f.fps)) : 0,
      },
      memory: {
        heapUsed: memArr.length > 0 ? memArr[memArr.length - 1].heapUsed : 0,
        heapTotal: memArr.length > 0 ? memArr[memArr.length - 1].heapTotal : 0,
        rss: memArr.length > 0 ? memArr[memArr.length - 1].rss : 0,
      },
      cpu: {
        current: cpuArr.length > 0 ? cpuArr[cpuArr.length - 1].percent : 0,
        avg: avg(cpuArr, 'percent'),
      },
      latency: {
        current: latArr.length > 0 ? latArr[latArr.length - 1].ms : 0,
        avg: avg(latArr, 'ms'),
      },
      samples: fpsArr.length,
    };
  }

  /**
   * 检测瓶颈
   */
  detectBottlenecks() {
    const snap = this.getSnapshot();
    const issues = [];

    if (parseFloat(snap.memory.heapUsed) > 500) {
      issues.push({ severity: 'warning', message: `内存使用过高: ${snap.memory.heapUsed}MB`, suggestion: '考虑清除缓存、关闭不用的标签页' });
    }
    if (parseFloat(snap.cpu.avg) > 50) {
      issues.push({ severity: 'warning', message: `CPU 使用率偏高: ${snap.cpu.avg}%`, suggestion: '检查是否有死循环或大量计算' });
    }
    if (parseFloat(snap.latency.avg) > 500) {
      issues.push({ severity: 'error', message: `API 延迟过高: ${snap.latency.avg}ms`, suggestion: '检查本地 LLM 服务是否正常运行' });
    }
    if (snap.fps.current < 30 && snap.samples > 10) {
      issues.push({ severity: 'warning', message: `渲染帧率过低: ${snap.fps.current} FPS`, suggestion: '关闭 GPU 加速不必要的功能或减少动画' });
    }

    return { issues, snapshot: snap };
  }

  /**
   * 生成性能报告
   */
  getReport() {
    const snap = this.getSnapshot();
    const bottlenecks = this.detectBottlenecks();

    return {
      timestamp: new Date().toISOString(),
      system: {
        platform: process.platform,
        arch: process.arch,
        nodeVersion: process.version,
        electronVersion: process.versions.electron,
        chromeVersion: process.versions.chrome,
      },
      metrics: snap,
      bottlenecks: bottlenecks.issues,
      recommendations: bottlenecks.issues.map(i => i.suggestion),
    };
  }
}

module.exports = { PerfMonitor };