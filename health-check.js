const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  conn.exec(`
echo "=== PM2 STATUS ==="
pm2 list 2>&1
echo ""
echo "=== NEXUS-HUB TEST ==="
curl -s http://localhost:3001/api/status 2>&1 | head -c 200
echo ""
echo "=== PYTHON BACKEND TEST ==="
curl -s http://localhost:8000/docs 2>&1 | head -c 100
echo ""
echo "=== AGENT STREAM TEST ==="
curl -s -X POST http://localhost:3001/api/agent/chat/stream -H "Content-Type: application/json" -d '{"task":"1+1=?","maxIterations":1}' 2>&1 | head -c 200
echo ""
echo "=== KLING TEST ==="
curl -s "http://localhost:3001/api/kling/task?id=test" 2>&1 | head -c 100
echo ""
echo "=== MESHY TEST ==="
curl -s http://localhost:3001/api/meshy/result/test123 2>&1 | head -c 100
echo ""
echo "=== DISK ==="
df -h / 2>&1 | tail -1
echo "=== MEMORY ==="
free -h 2>&1 | grep Mem
  `, (err, stream) => {
    if (err) { console.error('Error:', err.message); conn.end(); return; }
    let out = '';
    stream.on('data', d => out += d);
    stream.on('close', () => {
      console.log(out);
      conn.end();
    });
  });
});
conn.on('error', err => { console.error('Error:', err.message); });
conn.connect({ host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 30000 });
