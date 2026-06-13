const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 当前 Nginx 配置 ====="`,
  `cat /etc/nginx/conf.d/j3trisheng.conf`,
  `echo "===== default-trizen.conf ====="`,
  `cat /etc/nginx/conf.d/default-trizen.conf 2>/dev/null`,
  `echo "===== 测试主站 ====="`,
  `curl -4 -s -D - http://127.0.0.1/ 2>&1 | head -10`,
  `curl -4 -s -o /dev/null -w "main-index html check: %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/main-index.html`,
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
