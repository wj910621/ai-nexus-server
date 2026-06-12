const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接，检查 .env 文件...');

  conn.exec('echo "=== /home/admin/ai-nexus/.env ==="; cat /home/admin/ai-nexus/.env 2>/dev/null || echo "NOT FOUND"; echo "=== /home/admin/.env ==="; cat /home/admin/.env 2>/dev/null || echo "NOT FOUND"', (err, stream) => {
    if (err) { console.log('error:', err); conn.end(); return; }
    stream.on('data', d => process.stdout.write(d));
    stream.on('close', () => conn.end());
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
