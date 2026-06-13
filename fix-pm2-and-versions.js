const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  // 杀掉 admin 用户启动的进程，然后 PM2 启动
  `echo "===== 杀掉旧进程 ====="`,
  `kill -9 36973 2>/dev/null; sleep 1; echo "killed"`,
  `echo "===== PM2 启动 ====="`,
  `cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1 | tail -5`,
  `pm2 save 2>&1`,
  `echo "===== 验证 ====="`,
  `sleep 2 && pm2 list 2>&1 | head -5`,
  `curl -s -o /dev/null -w "API status: %{http_code}\\n" http://localhost:3001/`,
  `curl -s -o /dev/null -w "API studio: %{http_code}\\n" http://localhost:3001/studio/`,
  
  // 检查 server.js 版本
  `echo "===== server.js 版本 ====="`,
  `head -5 /home/admin/ai-nexus/server.js`,
  `grep "version" /home/admin/ai-nexus/server.js | head -5`,
  `wc -l /home/admin/ai-nexus/server.js`,
  
  // 检查本地 server.js
  `echo "===== 本地 server.js ====="`,
];
const fs = require('fs');
const localLines = fs.readFileSync('G:/大模型聚合网站/server.js', 'utf-8').split('\n').length;

conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) {
    console.log(`\n===== 本地 server.js =====`);
    console.log(`本地 server.js 行数: ${localLines}`);
    conn.end();
    return;
  }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
