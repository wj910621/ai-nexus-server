const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查当前 Nginx 配置 ====="`,
  `cat /etc/nginx/conf.d/j3trisheng.conf`,
  `echo "===== 检查 /studio/ 目录 ====="`,
  `ls -la /home/admin/nexus-studio/`,
  `echo "===== 检查 index.html 存在 ====="`,
  `test -f /home/admin/nexus-studio/index.html && echo "index.html EXISTS" || echo "index.html MISSING"`,
  `echo "===== 检查 Nginx 错误日志 ====="`,
  `tail -10 /var/log/nginx/error.log`,
  `echo "===== 用正确 Host 测试 ====="`,
  `curl -s -o /dev/null -w "Host=j3trisheng.com /studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "No Host /studio/ -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "Host=120.79.17.184 /studio/ -> %{http_code}\\n" -H "Host: 120.79.17.184" http://127.0.0.1/studio/`,
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
