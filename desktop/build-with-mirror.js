// 设置国内镜像和本地缓存后执行 electron-builder
const path = require('path');
const fs = require('fs');

// 将 electron 缓存目录设为项目内
const cacheDir = path.join(__dirname, '.electron-cache');
fs.mkdirSync(cacheDir, { recursive: true });

process.env.ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/';
process.env.ELECTRON_BUILDER_BINARIES_MIRROR = 'https://npmmirror.com/mirrors/electron-builder-binaries/';
process.env.ELECTRON_DOWNLOAD_MIRROR = 'https://npmmirror.com/mirrors/electron/';
process.env.ELECTRON_CACHE = cacheDir;

const { spawn } = require('child_process');
const args = process.argv.slice(2);
const child = spawn('node', ['node_modules/electron-builder/out/cli/cli.js', ...args], {
  stdio: 'inherit',
  shell: false,
  env: process.env
});
child.on('close', (code) => process.exit(code));
