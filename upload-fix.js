const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接服务器，上传修复文件...');

  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP error:', err); conn.end(); return; }

    const localDir = 'D:/OneDrive/文档/Nexus AI Studio 2/nexus-ai-studio';
    const uploads = [
      // 修复后的 sw.js → nexus-studio
      { local: path.join(localDir, 'sw.js'), remote: '/home/admin/nexus-studio/sw.js' },
      // 修复后的 server.js → ai-nexus
      { local: 'G:/大模型聚合网站/server.js', remote: '/home/admin/ai-nexus/server.js' },
    ];

    let pending = uploads.length;
    for (const u of uploads) {
      sftp.fastPut(u.local, u.remote, (err) => {
        if (err) console.error('❌', path.basename(u.local), err.message);
        else console.log('✅', path.basename(u.local));
        pending--;
        if (pending === 0) {
          console.log('\n🎉 修复文件上传完成！');
          sftp.end();
          conn.end();
        }
      });
    }
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
