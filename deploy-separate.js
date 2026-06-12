const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接，上传前端分离版本...');

  conn.sftp((err, sftp) => {
    if (err) { conn.end(); return; }

    // 创建 js 目录
    conn.exec('mkdir -p /home/admin/nexus-studio/js', () => {});

    // 上传文件: index.html + js 目录下所有文件
    const frontendDir = 'D:/OneDrive/文档/Nexus AI Studio 2/nexus-ai-studio';
    const studioDir = '/home/admin/nexus-studio';

    const uploads = [
      { local: frontendDir + '/index.html', remote: studioDir + '/index.html' },
    ];

    // 添加所有 js 文件
    const jsFiles = ['storage.js','api.js','models.js','chat.js','code.js','agent.js','skills.js','plugin.js','particles.js','autonomous.js','knowledge.js','ui.js','app.js'];
    for (const f of jsFiles) {
      uploads.push({ local: frontendDir + '/js/' + f, remote: studioDir + '/js/' + f });
    }

    let pending = uploads.length;
    for (const u of uploads) {
      sftp.fastPut(u.local, u.remote, (err) => {
        if (err) console.error('❌', path.basename(u.local), err.message);
        else console.log('✅', path.basename(u.local));
        pending--;
        if (pending === 0) {
          console.log('\n🎉 分离版前端上传完成！');
          sftp.end();
          conn.end();
        }
      });
    }
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
