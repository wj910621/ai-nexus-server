const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接，检查 Nginx 状态...');

  conn.exec('nginx -t 2>&1; echo "==="; curl -s -H "Host: j3trisheng.com" http://127.0.0.1/api/status 2>&1 | head -3', (err, stream) => {
    if (err) { console.log('error:', err); conn.end(); return; }
    stream.on('data', d => process.stdout.write(d));
    stream.on('close', () => {
      console.log('\n---');
      conn.end();
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
