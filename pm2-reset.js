const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

conn.on('ready', () => {
  conn.exec(`
set -e
echo "=== Step 1: Kill everything on port 3001 ==="
fuser -k 3001/tcp 2>/dev/null || true
sleep 2

echo "=== Step 2: Kill all node server.js processes ==="
ps aux | grep "node server" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
sleep 2

echo "=== Step 3: Reset PM2 ==="
pm2 kill 2>/dev/null || true
sleep 1
pm2 resurrect 2>/dev/null || true
sleep 1

echo "=== Step 4: Delete old status and start fresh ==="
pm2 delete nexus-hub 2>/dev/null || true
pm2 delete nexus-python 2>/dev/null || true
pm2 delete pm2-logrotate 2>/dev/null || true

echo "=== Step 5: Start nexus-hub ==="
cd /home/admin/ai-nexus
pm2 start server.js --name nexus-hub --update-env 2>&1
sleep 3

echo "=== Step 6: Start nexus-python ==="
cd /home/admin/ai-nexus/python-backend
pm2 start run.sh --name nexus-python --interpreter bash 2>&1
sleep 3

echo "=== Step 7: Start pm2-logrotate ==="
pm2 install pm2-logrotate 2>/dev/null || true
sleep 1

echo "=== Step 8: Save ==="
pm2 save --force 2>&1

echo ""
echo "=== FINAL STATUS ==="
pm2 list 2>&1
echo ""
echo "=== HUB TEST ==="
curl -s http://localhost:3001/api/status | head -c 100
echo ""
echo "=== PYTHON TEST ==="
curl -s http://localhost:8000/docs | head -c 100
echo ""
echo "=== DONE ==="
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
conn.connect({ host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 60000 });
