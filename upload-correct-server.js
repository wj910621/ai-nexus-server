const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;
const REMOTE_DIR = '/home/admin/ai-nexus';
const NVM = 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";';

conn.on('ready', () => {
  console.log('已连接，上传正确的 server.js...');

  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP error:', err); conn.end(); return; }

    // 上传正确版本的 server.js（从本地完整版）
    const localServerJs = path.join(__dirname, 'server.js');
    const remotePath = path.posix.join(REMOTE_DIR, 'server.js');

    console.log('上传 server.js (' + fs.statSync(localServerJs).size + ' bytes)...');
    const writeStream = sftp.createWriteStream(remotePath);
    const readStream = fs.createReadStream(localServerJs);
    readStream.pipe(writeStream);
    writeStream.on('close', () => {
      console.log('server.js 上传完成');

      // 确认上传成功
      conn.exec('wc -c /home/admin/ai-nexus/server.js', (err, stream) => {
        if (err) { console.log('check error:', err); conn.end(); return; }
        stream.on('data', d => process.stdout.write(d));
        stream.on('close', () => {
          console.log('---');

          // 如果还有旧的 data.db，删掉重建
          conn.exec('rm -f /home/admin/ai-nexus/data.db; echo "old db removed"', (err, stream) => {
            if (err) { console.log('check error:', err); conn.end(); return; }
            stream.on('data', d => process.stdout.write(d));
            stream.on('close', () => {
              console.log('---');

              // 杀掉旧进程，重新安装依赖，启动
              conn.exec('pkill -f "node server.js" 2>/dev/null; sleep 2; echo "killed"; ' + NVM + ' cd ' + REMOTE_DIR + ' && setsid node server.js > /tmp/ai-nexus.log 2>&1 & sleep 6 && node -e "require(\'http\').get(\'http://localhost:3001/api/status\', r=>{let d=\'\';r.on(\'data\',c=>d+=c);r.on(\'end\',()=>console.log(d))}).on(\'error\',()=>console.log(\'API not ready\'))"', (err, stream) => {
                if (err) { console.log('start error:', err); conn.end(); return; }
                stream.on('data', d => process.stdout.write(d));
                stream.stderr.on('data', d => process.stdout.write(d));
                stream.on('close', () => {
                  console.log('\n--- 启动完成 ---');
                  conn.end();
                });
              });
            });
          });
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
