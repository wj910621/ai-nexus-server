const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 所有相关文件 ====="`,
  `find /home -name "index.html" -o -name "dashboard.html" -o -name "landing.html" 2>/dev/null`,
  `echo "===== 端口 3001 占用 ====="`,
  `ss -tlnp | grep 3001`,
  `echo "===== systemctl nginx ====="`,
  `systemctl status nginx 2>&1 | head -3`,
  `echo "===== 通过 Nginx 访问 ====="`,
  `curl -4 -s -o /dev/null -w "Nginx studio: %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `curl -4 -s -o /dev/null -w "Nginx root: %{http_code}\\n" http://127.0.0.1/`,
  `echo "===== DMX API 测试 ====="`,
  `grep "DMXAPI\|OPENAI_API_KEY\|dmxapi" /home/admin/ai-nexus/.env | head -3`,
  `echo "===== 测试单模型 ====="`,
  `curl -s -X POST http://localhost:3001/api/chat -H "Content-Type: application/json" -d '{"model":"gpt4o","message":"hi"}' 2>&1 | head -100`,
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
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: CHANGE_ME });
