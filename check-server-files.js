const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查服务器文件 ====="`,
  `ls -la /home/admin/nexus-studio/index.html`,
  `ls -la /home/admin/ai-nexus/dashboard.html`,
  `ls -la /home/admin/ai-nexus/index.html 2>/dev/null || echo "no index.html in ai-nexus"`,
  `echo "===== 检查 index.html 中的品牌 ====="`,
  `grep -o "TriGen\|Nexus Hub" /home/admin/nexus-studio/index.html | head -5`,
  `echo "===== 检查 dashboard.html 中的品牌 ====="`,
  `grep -o "TriGen\|Nexus Hub" /home/admin/ai-nexus/dashboard.html | head -5`,
  `echo "===== 检查后端 API ====="`,
  `curl -s http://localhost:3001/api/status 2>&1 || echo "API status check failed"`,
  `curl -s http://localhost:3001/api/models 2>&1 | head -100 || echo "models check failed"`,
  `echo "===== PM2 状态 ====="`,
  `pm2 list`,
];
conn.on('ready', () => { console.log('Connected'); run(0); });
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
