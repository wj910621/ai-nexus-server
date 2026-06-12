const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';
const FRONTEND = 'D:/OneDrive/文档/Nexus AI Studio 2/nexus-ai-studio';
const STUDIO = '/home/admin/nexus-studio';

conn.on('ready', () => {
  console.log('已连接，先创建目录再上传...');

  conn.exec('mkdir -p ' + STUDIO + '/js ' + STUDIO + '/css', (err, stream) => {
    if (err) { console.log('mkdir error:', err); conn.end(); return; }
    stream.on('close', () => {
      console.log('目录创建完成');

      conn.sftp((err, sftp) => {
        if (err) { conn.end(); return; }

        const uploads = [
          { local: path.join(FRONTEND, 'index.html'), remote: path.posix.join(STUDIO, 'index.html') },
          { local: path.join(FRONTEND, 'css/style.css'), remote: path.posix.join(STUDIO, 'css/style.css') },
          { local: path.join(FRONTEND, 'sw.js'), remote: path.posix.join(STUDIO, 'sw.js') },
          { local: path.join(FRONTEND, 'manifest.json'), remote: path.posix.join(STUDIO, 'manifest.json') },
        ];

        const jsFiles = ['storage.js','api.js','models.js','chat.js','code.js','agent.js','skills.js','plugin.js','particles.js','autonomous.js','knowledge.js','ui.js','app.js','worker.js'];
        for (const f of jsFiles) {
          uploads.push({ local: path.join(FRONTEND, 'js', f), remote: path.posix.join(STUDIO, 'js', f) });
        }

        let pending = uploads.length;
        for (const u of uploads) {
          sftp.fastPut(u.local, u.remote, (err) => {
            if (err) console.error('❌', path.basename(u.local));
            else console.log('✅', path.basename(u.local));
            pending--;
            if (pending === 0) {
              console.log('\n🎉 模块化前端上传完成！');
              console.log('请访问: http://120.79.17.184:3001/studio/');
              sftp.end();
              conn.end();
            }
          });
        }
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
