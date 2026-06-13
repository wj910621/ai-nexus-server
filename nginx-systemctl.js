const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 将 Nginx 切换到 systemctl ====="`,
  `nginx -s stop 2>&1; sleep 1; echo "nginx stopped"`,
  `systemctl start nginx 2>&1; echo "systemctl start done"`,
  `systemctl status nginx 2>&1 | head -5`,
  `echo "===== 验证 ====="`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "j3trisheng.com:80 -> %{http_code}\\n" -m 10 http://j3trisheng.com/ 2>&1`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
