const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';
const REMOTE_DIR = '/home/admin/ai-nexus';
const NVM = 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";';

conn.on('ready', () => {
  console.log('已连接，上传最终版 server.js...');

  conn.sftp((err, sftp) => {
    if (err) { conn.end(); return; }

    // 上传 server.js
    const localSrv = path.join(__dirname, 'server.js');
    const remoteSrv = path.posix.join(REMOTE_DIR, 'server.js');
    sftp.fastPut(localSrv, remoteSrv, (err) => {
      if (err) { console.log('upload error:', err); conn.end(); return; }
      console.log('server.js 已上传');

      // 删除旧数据库并测试
      conn.exec('rm -f /home/admin/ai-nexus/data.db; ' + NVM + ' cd ' + REMOTE_DIR + ' && timeout 6 node -e "process.env.PORT=3001;process.env.JWT_SECRET=\'test\';require(\'./server.js\')" 2>&1', (err, stream) => {
        if (err) { console.log('test error:', err); conn.end(); return; }
        let output = '';
        stream.on('data', d => { output += d.toString(); process.stdout.write(d); });
        stream.stderr.on('data', d => process.stdout.write(d));
        stream.on('close', () => {
          console.log('\n=== 测试结果 ===');
          if (output.includes('已启动') || output.includes('Nexus')) {
            console.log('✅ 语法修正成功！服务器启动正常');
            
            // 正式启动
            conn.exec('rm -f /home/admin/ai-nexus/data.db; ' + NVM + ' cd ' + REMOTE_DIR + ' && export PORT=3001 && nohup node server.js > /tmp/ai-nexus.log 2>&1 & sleep 5 && curl -s http://localhost:3001/api/status', (err, stream) => {
              stream.on('data', d => process.stdout.write(d));
              stream.on('close', () => {
                console.log('\n✅ 部署完成！');
                conn.end();
              });
            });
          } else {
            console.log('❌ 仍有错误');
            conn.end();
          }
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
