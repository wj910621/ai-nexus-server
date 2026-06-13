const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `echo "===== PM2 修复 ====="`,
  // 先停掉当前占用 3001 的进程
  `kill -9 $(lsof -t -i:3001) 2>/dev/null; echo "killed old process"`,
  `sleep 1`,
  // 重启 PM2
  `cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1 | tail -10`,
  `pm2 save 2>&1`,
  `pm2 list 2>&1`,
  
  `echo "===== 后端 3001 根路径测试 ====="`,
  `sleep 2`,
  `curl -s -o /dev/null -w "localhost:3001/ -> %{http_code}\\n" http://localhost:3001/`,
  `curl -s -o /dev/null -w "localhost:3001/studio/ -> %{http_code}\\n" http://localhost:3001/studio/`,
  `curl -s -o /dev/null -w "localhost:3001/api/ -> %{http_code}\\n" http://localhost:3001/api/`,
  
  `echo "===== 后端日志 ====="`,
  `pm2 logs nexus-hub --lines 15 --nostream 2>&1 | tail -20`,
  
  `echo "===== 服务器信息 ====="`,
  `ip addr show | grep "inet " | grep -v 127.0.0.1`,
  `curl -s ifconfig.me 2>&1`,
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
