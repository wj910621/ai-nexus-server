const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

const commands = [
  `echo "===== Host 头测试 ====="`,
  `curl -s -o /dev/null -w "j3trisheng.com:80/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/`,
  `curl -s -o /dev/null -w "j3trisheng.com:80/studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "j3trisheng.com:80/api/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/api/`,
  `curl -s -o /dev/null -w "www.j3trisheng.com:80/studio/ -> %{http_code}\\n" -H "Host: www.j3trisheng.com" http://127.0.0.1/studio/`,
  `echo "===== 公网 IP 带 Host 头 ====="`,
  `curl -s -o /dev/null -w "IP:80/studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://120.79.17.184/studio/`,
  `curl -s -o /dev/null -w "IP:80/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://120.79.17.184/`,
  `echo "===== 从外网测试 ====="`,
  `curl -s -o /dev/null -w "http://j3trisheng.com -> %{http_code}\\n" -m 10 http://j3trisheng.com 2>&1`,
  `curl -s -o /dev/null -w "http://j3trisheng.com/studio/ -> %{http_code}\\n" -m 10 http://j3trisheng.com/studio/ 2>&1`,
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
