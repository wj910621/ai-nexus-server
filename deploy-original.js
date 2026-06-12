const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';
const SRC = 'D:/OneDrive/文档/Nexus AI Studio 2/nexus-ai-studio';
const DST = '/home/admin/nexus-studio';

conn.on('ready', () => {
  console.log('已连接，上传原始模块化版本...');

  // 先清理并创建目录
  conn.exec('rm -rf ' + DST + '/* && mkdir -p ' + DST + '/js ' + DST + '/css', (err) => {
    if (err) { console.log('mkdir error:', err); conn.end(); return; }

    conn.sftp((err, sftp) => {
      if (err) { conn.end(); return; }

      const files = [
        { local: path.join(SRC, 'index.html'), remote: path.posix.join(DST, 'index.html') },
        { local: path.join(SRC, 'css/style.css'), remote: path.posix.join(DST, 'css/style.css') },
        { local: path.join(SRC, 'manifest.json'), remote: path.posix.join(DST, 'manifest.json') },
        { local: path.join(SRC, 'sw.js'), remote: path.posix.join(DST, 'sw.js') },
      ];

      const jsFiles = ['storage.js','api.js','models.js','chat.js','code.js','agent.js','skills.js','plugin.js','particles.js','autonomous.js','knowledge.js','ui.js','app.js'];
      for (const f of jsFiles) {
        files.push({ local: path.join(SRC, 'js', f), remote: path.posix.join(DST, 'js', f) });
      }

      let pending = files.length;
      for (const f of files) {
        sftp.fastPut(f.local, f.remote, (err) => {
          if (err) console.error('❌', path.basename(f.local), err.message);
          else console.log('✅', path.basename(f.local));
          pending--;
          if (pending === 0) {
            console.log('\n🎉 原始模块化版本上传完成！');
            sftp.end();
            conn.end();
          }
        });
      }
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
