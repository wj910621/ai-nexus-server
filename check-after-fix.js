const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  conn.exec('echo "=== PM2 ===" && pm2 list 2>&1 && echo "=== HUB ===" && curl -s http://localhost:3001/api/status | head -c 100 && echo "" && echo "=== PYTHON ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 && echo ""', (err, stream) => {
    let out = '';
    stream.on('data', d => out += d);
    stream.on('close', () => {
      console.log(out);
      conn.end();
    });
  });
});
conn.on('error', err => { console.error('Error:', err.message); });
conn.connect({ host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 15000 });
