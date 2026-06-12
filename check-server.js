const { Client } = require('ssh2');
const http = require('http');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接，检查服务器上 index.html 的前几行...');

  conn.exec('head -20 /home/admin/nexus-studio/index.html; echo "===CACHE==="; tail -5 /home/admin/nexus-studio/index.html', (err, stream) => {
    if (err) { console.log('error:', err); conn.end(); return; }
    stream.on('data', d => process.stdout.write(d));
    stream.on('close', () => {
      console.log('\n--- done ---');

      // 也从 Nginx 获取看看是否一致
      http.get('http://127.0.0.1/studio/index.html', (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          console.log('Nginx served:', data.substring(0, 100));
          conn.end();
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
