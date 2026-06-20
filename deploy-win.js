/**
 * TriGen 一键部署脚本 (Windows 版)
 * 
 * 使用方法（在 Git Bash 或 PowerShell 中执行）：
 *   export DEPLOY_PASS=你的服务器密码
 *   node deploy-win.js [frontend|backend|env|all]
 * 
 * 示例：
 *   set DEPLOY_PASS=Wjzlt910621.      (CMD)
 *   $env:DEPLOY_PASS="Wjzlt910621."    (PowerShell)
 *   export DEPLOY_PASS=Wjzlt910621.    (Git Bash)
 *   node deploy-win.js all
 */
const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const DEPLOY_PASS = process.env.DEPLOY_PASS;
const HOST = '120.79.17.184';
const USER = 'root';
const FRONTEND_DIR = '/home/admin/nexus-studio';
const BACKEND_DIR = '/home/admin/ai-nexus';
const BASE = 'G:/大模型聚合网站';

if (!DEPLOY_PASS) {
  console.error('❌ 错误：未设置 DEPLOY_PASS 环境变量');
  console.error('   在 PowerShell 中执行: $env:DEPLOY_PASS="你的密码"');
  console.error('   在 Git Bash 中执行:   export DEPLOY_PASS=你的密码');
  process.exit(1);
}

const mode = process.argv[2] || 'all';
let pending = 0;
let hasError = false;

function sshExec(cmd, cb) {
  const conn = new Client();
  conn.on('ready', () => {
    conn.exec(cmd, (err, stream) => {
      if (err) { console.error(`[ERR] ${err.message}`); cb(err); conn.end(); return; }
      let out = '';
      stream.on('data', d => out += d);
      stream.on('stderr', d => out += d);
      stream.on('close', () => { cb(null, out); conn.end(); });
    });
  });
  conn.on('error', err => { console.error(`[SSH ERR] ${err.message}`); cb(err); });
  conn.connect({ host: HOST, port: 22, username: USER, password: DEPLOY_PASS, readyTimeout: 10000 });
}

function uploadFile(local, remote, cb) {
  const conn = new Client();
  conn.on('ready', () => {
    const dir = remote.substring(0, remote.lastIndexOf('/'));
    conn.exec(`mkdir -p ${dir}`, () => {
      conn.sftp((err, sftp) => {
        if (err) { console.error(`[SFTP ERR] ${err.message}`); conn.end(); cb(err); return; }
        sftp.fastPut(local, remote, err2 => {
          if (err2) console.error(`  ❌ ${path.basename(local)}`);
          else console.log(`  ✅ ${path.basename(local)}`);
          sftp.end();
          conn.end();
          cb(err2);
        });
      });
    });
  });
  conn.on('error', err => { console.error(`[SSH ERR] ${err.message}`); cb(err); });
  conn.connect({ host: HOST, port: 22, username: USER, password: DEPLOY_PASS, readyTimeout: 10000 });
}

function uploadDir(localDir, remoteDir, cb) {
  if (!fs.existsSync(localDir)) { console.log(`  ⚠️ 目录不存在: ${localDir}`); cb(null); return; }
  const items = fs.readdirSync(localDir);
  let completed = 0;
  const total = items.length;
  if (total === 0) { cb(null); return; }
  items.forEach(item => {
    const lp = path.join(localDir, item);
    const rp = remoteDir + '/' + item;
    if (fs.statSync(lp).isDirectory()) {
      uploadDir(lp, rp, () => { completed++; if (completed >= total) cb(null); });
    } else {
      uploadFile(lp, rp, () => { completed++; if (completed >= total) cb(null); });
    }
  });
}

function deployFrontend(cb) {
  console.log('\n🌐 [前端] 部署前端文件...');
  uploadFile(BASE + '/index.html', FRONTEND_DIR + '/index.html', () => {
    uploadFile(BASE + '/landing.html', FRONTEND_DIR + '/landing.html', () => {
      uploadFile(BASE + '/dashboard.html', FRONTEND_DIR + '/dashboard.html', () => {
        console.log('📁 上传 js/ 目录...');
        uploadDir(BASE + '/js', FRONTEND_DIR + '/js', cb);
      });
    });
  });
}

function deployBackend(cb) {
  console.log('\n⚙️  [后端] 部署 API Server...');
  uploadFile(BASE + '/server.js', BACKEND_DIR + '/server.js', () => {
    console.log('🔄 重启服务...');
    sshExec('fuser -k 3001/tcp 2>/dev/null; sleep 1; cd ' + BACKEND_DIR + ' && pm2 delete nexus-hub 2>/dev/null; pm2 start server.js --name nexus-hub -f --update-env 2>&1', (err, out) => {
      if (err) console.error('  ❌ 重启失败');
      else { console.log('  ✅ 服务已重启'); if(out) console.log(out.substring(0,200)); }
      cb();
    });
  });
}

function deployEnv(cb) {
  console.log('\n🔑 [环境] 部署 .env 配置...');
  uploadFile(BASE + '/.env', BACKEND_DIR + '/.env', () => {
    console.log('🔄 重启服务...');
    sshExec('fuser -k 3001/tcp 2>/dev/null; sleep 1; cd ' + BACKEND_DIR + ' && pm2 delete nexus-hub 2>/dev/null; pm2 start server.js --name nexus-hub -f --update-env 2>&1', (err, out) => {
      if (err) console.error('  ❌ 重启失败');
      else { console.log('  ✅ 服务已重启'); if(out) console.log(out.substring(0,200)); }
      cb();
    });
  });
}

console.log('========================================');
console.log('  TriGen 一键部署 (Windows 版)');
console.log('  ' + new Date().toLocaleString());
console.log('========================================\n');

switch(mode) {
  case 'frontend':
    deployFrontend(() => { console.log('\n🎉 前端部署完成！'); });
    break;
  case 'backend':
    deployBackend(() => { console.log('\n🎉 后端部署完成！'); });
    break;
  case 'env':
    deployEnv(() => { console.log('\n🎉 环境变量更新完成！'); });
    break;
  case 'all':
  default:
    deployFrontend(() => {
      deployBackend(() => {
        console.log('\n🎉 全量部署完成！');
        console.log('   🌐 https://j3trisheng.com');
      });
    });
    break;
}
