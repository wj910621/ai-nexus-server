const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `echo "===== IPv4 测试 ====="`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/ -> %{http_code}\\n" http://127.0.0.1/`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `echo "===== 添加 IPv6 监听 ====="`,
  `sed -i 's/listen 80;/listen 80;\\n    listen [::]:80;/' /etc/nginx/conf.d/j3trisheng.conf`,
  `head -5 /etc/nginx/conf.d/j3trisheng.conf`,
  `echo "===== 测试并重载 ====="`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  `echo "===== IPv6 测试 ====="`,
  `curl -6 -s -o /dev/null -w "::1:80/ -> %{http_code}\\n" http://localhost/`,
  `curl -6 -s -o /dev/null -w "::1:80/studio/ -> %{http_code}\\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "default:80/studio/ -> %{http_code}\\n" http://localhost/studio/`,
  `curl -s -H "Host: j3trisheng.com" -o /dev/null -w "j3trisheng.com:80/studio/ -> %{http_code}\\n" http://localhost/studio/`,
  `echo "===== 公网测试 ====="`,
  `curl -s -o /dev/null -w "120.79.17.184:80/ -> %{http_code}\\n" http://120.79.17.184/`,
  `curl -s -o /dev/null -w "120.79.17.184:80/studio/ -> %{http_code}\\n" http://120.79.17.184/studio/`,
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
