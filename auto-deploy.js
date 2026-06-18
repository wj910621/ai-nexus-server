/**
 * TriGen 一键自动部署脚本
 * 上传文件到服务器并重启服务
 */
const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;
const FRONTEND_DIR = '/home/admin/nexus-studio';
const BACKEND_DIR = '/home/admin/ai-nexus';
const BASE = 'G:/大模型聚合网站';

const filesToUpload = [
  // 前端文件
  { local: path.join(BASE, 'index.html'), remote: FRONTEND_DIR + '/index.html' },
  { local: path.join(BASE, 'landing.html'), remote: FRONTEND_DIR + '/landing.html' },
  // js 目录（递归上传）
  { local: path.join(BASE, 'js'), remote: FRONTEND_DIR + '/js', recursive: true },
  // 后端文件
  { local: path.join(BASE, 'server.js'), remote: BACKEND_DIR + '/server.js' },
];

const conn = new Client();
let pendingUploads = 0;
let hasError = false;

function uploadFile(local, remote, cb) {
  const sftp = conn.sftp((err, sftp) => {
    if (err) { console.error('❌ SFTP error:', err.message); cb(err); return; }
    const rOpts = remote.replace(/\/[^/]+$/, '');
    // 确保远程目录存在
    conn.exec(`mkdir -p ${rOpts}`, (err2, stream) => {
      if (err2) { console.error('❌ mkdir error:', err2.message); }
      let d = '';
      stream.on('data', c => d += c);
      stream.on('close', () => {
        const rname = path.basename(remote);
        sftp.fastPut(local, remote, (err3) => {
          if (err3) {
            console.error(`❌ 上传失败: ${rname}: ${err3.message}`);
            hasError = true;
          } else {
            console.log(`  ✅ ${rname} -> ${remote}`);
          }
          sftp.end();
          cb(err3);
        });
      });
    });
  });
}

function uploadDir(localDir, remoteDir, cb) {
  if (!fs.existsSync(localDir)) { console.log(`  ⚠️ 目录不存在: ${localDir}`); cb(null); return; }
  const items = fs.readdirSync(localDir);
  let completed = 0;
  const total = items.length;
  if (total === 0) { cb(null); return; }
  
  // 先创建远程目录
  conn.exec(`mkdir -p ${remoteDir}`, () => {
    items.forEach(item => {
      const localPath = path.join(localDir, item);
      const remotePath = remoteDir + '/' + item;
      const stat = fs.statSync(localPath);
      if (stat.isDirectory()) {
        uploadDir(localPath, remotePath, () => {
          completed++;
          if (completed >= total) cb(null);
        });
      } else {
        conn.sftp((err, sftp) => {
          if (err) { completed++; if (completed >= total) cb(null); return; }
          sftp.fastPut(localPath, remotePath, (err2) => {
            if (err2) {
              console.error(`  ❌ 上传失败: ${item}: ${err2.message}`);
            } else {
              console.log(`  ✅ js/${item} -> ${remotePath}`);
            }
            sftp.end();
            completed++;
            if (completed >= total) cb(null);
          });
        });
      }
    });
  });
}

console.log('🚀 开始部署 TriGen...\n');
console.log(`  服务器: ${USER}@${HOST}`);
console.log(`  前端目录: ${FRONTEND_DIR}`);
console.log(`  后端目录: ${BACKEND_DIR}\n`);

// 第一步：清除 known_hosts
const { execSync } = require('child_process');
try {
  execSync(`ssh-keygen -R ${HOST} 2>nul || true`, { stdio: 'ignore' });
  console.log('  ✅ Host key 已清除');
} catch(e) {}
console.log('');

conn.on('ready', () => {
  console.log('✅ SSH 连接成功\n');
  
  // 上传 index.html
  console.log('📄 上传前端文件...');
  uploadFile(filesToUpload[0].local, filesToUpload[0].remote, () => {
    // 上传 landing.html
    uploadFile(filesToUpload[1].local, filesToUpload[1].remote, () => {
      // 上传 js 目录
      console.log('📁 上传 js/ 目录（含 i18n.js）...');
      uploadDir(path.join(BASE, 'js'), FRONTEND_DIR + '/js', () => {
        // 上传 server.js
        console.log('\n⚙️  上传后端文件...');
        uploadFile(filesToUpload[3].local, filesToUpload[3].remote, () => {
          console.log('\n📦 所有文件上传完成！');
          
          // 重启服务
          console.log('\n🔄 重启服务...');
          conn.exec('cd ' + BACKEND_DIR + ' && pm2 restart server.js', (err, stream) => {
            if (err) {
              console.error('❌ 重启失败:', err.message);
            } else {
              let out = '';
              stream.on('data', d => out += d);
              stream.on('stderr', d => out += d);
              stream.on('close', () => {
                console.log('  ' + out.trim().split('\n').join('\n  '));
                console.log('\n🎉 部署完成！');
                console.log('  🌐 https://j3trisheng.com');
                console.log('  ⚡ 多语言切换：侧边栏底部语言选择器');
                conn.end();
              });
            }
          });
        });
      });
    });
  });
});

conn.on('error', (err) => {
  console.error('❌ SSH 连接错误:', err.message);
  if (err.message.includes('authentication')) {
    console.log('\n💡 尝试使用密码认证...');
    // 服务器可能没有 SSH Key，尝试用密码重连
    conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
  } else if (err.message.includes('ETIMEDOUT')) {
    console.log('💡 连接超时，检查服务器是否在线');
  } else if (err.message.includes('ECONNREFUSED')) {
    console.log('💡 连接被拒绝，检查 SSH 服务是否运行');
  }
});

conn.connect({
  host: HOST,
  port: 22,
  username: USER,
  password: PASS,
  readyTimeout: 10000,
});
