const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接服务器，上传文件...');

  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP error:', err); conn.end(); return; }

    // 确保目录存在
    conn.exec('mkdir -p /home/admin/ai-nexus /home/admin/nexus-studio/css', () => {});

    const releaseDir = path.join(__dirname, 'nexus-release');
    const items = fs.readdirSync(releaseDir);
    let pending = 0;

    function uploadItem(localPath, remotePath) {
      pending++;
      sftp.fastPut(localPath, remotePath, (err) => {
        if (err) console.error('❌ 上传失败:', path.basename(localPath), err.message);
        else console.log('✅ 已上传:', path.basename(localPath));
        pending--;
        if (pending === 0) {
          console.log('\n🎉 所有文件上传完成！');
          sftp.end();
          conn.end();
        }
      });
    }

    for (const item of items) {
      const localPath = path.join(releaseDir, item);
      const stat = fs.statSync(localPath);
      if (stat.isFile()) {
        if (item === 'server.js' || item === 'package.json' || item === '.env') {
          uploadItem(localPath, '/home/admin/ai-nexus/' + item);
        } else if (item === 'index.html' || item === 'sw.js' || item === 'manifest.json') {
          uploadItem(localPath, '/home/admin/nexus-studio/' + item);
        } else if (item === 'style.css') {
          uploadItem(localPath, '/home/admin/nexus-studio/css/style.css');
        }
      } else if (stat.isDirectory() && item === 'css') {
        // upload css/style.css
        const cssFiles = fs.readdirSync(localPath);
        for (const cf of cssFiles) {
          uploadItem(path.join(localPath, cf), '/home/admin/nexus-studio/css/' + cf);
        }
      }
    }

    if (pending === 0) {
      console.log('\n🎉 所有文件上传完成！');
      sftp.end();
      conn.end();
    }
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
