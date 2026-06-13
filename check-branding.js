const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查 index.html 标题 ====="`,
  `head -22 /home/admin/nexus-studio/index.html | tail -5`,
  `echo "===== grep 检查 ====="`,
  `grep -c "TriGen" /home/admin/nexus-studio/index.html`,
  `echo "===== 文件大小和修改时间 ====="`,
  `ls -la /home/admin/nexus-studio/index.html /home/admin/ai-nexus/dashboard.html`,
  `echo "===== PM2 进程 ====="`,
  `fuser 3001/tcp 2>/dev/null`,
  `ps aux | grep server.js | grep -v grep | head -3`,
  `echo "===== 重启 PM2 ====="`,
  `pm2 delete nexus-hub 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; sleep 1; cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1 | tail -5; pm2 save 2>&1`,
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
