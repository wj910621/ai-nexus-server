const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  conn.exec(`
set -e
echo "=== Before ==="
pm2 list 2>&1 | head -10
echo ""

# Kill ALL node server processes
echo "Killing all node server processes..."
pkill -f "node server.js" 2>/dev/null || true
sleep 2

# Also kill any process on port 3001
fuser -k 3001/tcp 2>/dev/null || true
sleep 1

# Delete old PM2 entries
pm2 delete nexus-hub 2>/dev/null || true
pm2 delete nexus-python 2>/dev/null || true

# Restart both cleanly
echo ""
echo "=== Starting nexus-hub (Node.js) ==="
pm2 start /home/admin/ai-nexus/server.js --name nexus-hub --update-env 2>&1
sleep 3

echo ""
echo "=== Starting nexus-python (Python FastAPI) ==="
pm2 start /home/admin/ai-nexus/python-backend/run.sh --name nexus-python --interpreter bash 2>&1
sleep 3

echo ""
echo "=== After ==="
pm2 list 2>&1

echo ""
echo "=== NEXUS-HUB VERIFY ==="
curl -s http://localhost:3001/api/status | head -c 100
echo ""

echo "=== PYTHON VERIFY ==="
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs
echo ""

pm2 save
echo ""
echo "=== ALL DONE ==="
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
