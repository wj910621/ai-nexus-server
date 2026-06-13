const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查服务器原有 index.html ====="`,
  `find /home -name "*.html" -o -name "*.bak" -o -name "*.backup" 2>/dev/null | grep -i index`,
  `ls -la /home/admin/nexus-studio/`,
  `ls -la /home/admin/ai-nexus/ 2>/dev/null | head -20`,
  `echo "===== PM2 重新启动 ====="`,
  `fuser -k 3001/tcp 2>/dev/null; sleep 1`,
  `cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1 | tail -5`,
  `pm2 save 2>&1`,
  `sleep 2`,
  `echo "===== 测试 API ====="`,
  `curl -s -o /dev/null -w "port 3001 api: %{http_code}\\n" http://localhost:3001/api/models-count`,
  `curl -s -o /dev/null -w "port 3001 status: %{http_code}\\n" http://localhost:3001/api/status`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { console.log('Done'); conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
