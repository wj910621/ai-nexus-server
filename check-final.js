const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `echo "===== PM2 最终状态 ====="`,
  `pm2 list 2>&1`,
  `sleep 2`,
  `ss -tlnp | grep 3001`,
  `echo "===== Nginx 最终测试 ====="`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/api/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/api/`,
  `echo "===== SSL 准备 ====="`,
  `ls /etc/nginx/conf.d/`,
  `echo "===== Node 版本 ====="`,
  `node --version`,
  `npm --version`,
  `echo "===== 检查源文件 ====="`,
  `ls -la /home/admin/ai-nexus/package.json`,
  `cat /home/admin/ai-nexus/package.json`,
];

const conn = new Client();
conn.on('ready', () => { runCommands(0); });
conn.on('error', (err) => { console.error('Error:', err.message); process.exit(1); });
function runCommands(idx) {
  if (idx >= commands.length) { conn.end(); return; }
  conn.exec(commands[idx], (err, stream) => {
    if (err) { console.log('ERR:', err.message); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => { if (out.trim()) console.log(out.trim()); runCommands(idx + 1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
