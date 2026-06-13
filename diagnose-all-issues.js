const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查 Nginx 当前配置 ====="`,
  `cat /etc/nginx/conf.d/j3trisheng.conf | head -15`,
  `echo "===== 测试根路径 ====="`,
  `curl -4 -s -D - http://127.0.0.1/ 2>&1 | head -15`,
  `echo "===== 检查公网 IP ====="`,
  `curl -s -o /dev/null -w "公网: %{http_code}\\n" http://120.79.17.184/`,
  `echo "===== 检查管理员密码 ====="`,
  `grep "ADMIN_PASSWORD" /home/admin/ai-nexus/.env`,
  `grep "ADMIN_PASSWORD" /home/admin/ai-nexus/server.js`,
  `echo "===== 检查 .env 是否被读取 ====="`,
  `curl -s http://localhost:3001/api/status | head -200`,
  `echo "===== 检查积分逻辑 ====="`,
  `grep -n "30\|积分\|credit\|DEFAULT_CREDITS" /home/admin/ai-nexus/server.js | head -20`,
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
