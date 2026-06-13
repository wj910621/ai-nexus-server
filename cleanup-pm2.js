const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `echo "===== 清理 PM2 ====="`,
  // 停掉强力占用 3001 的进程
  `fuser -k 3001/tcp 2>/dev/null; sleep 2; echo "port cleared"`,
  // 删除旧的 PM2 进程
  `pm2 delete nexus-hub 2>&1`,
  // 重新启动
  `cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub --watch 2>&1 | tail -10`,
  `pm2 save 2>&1`,
  `pm2 list 2>&1`,
  `echo "===== PM2 开机自启 ====="`,
  `pm2 startup 2>&1 | tail -5`,
  `echo "===== 验证 ====="`,
  `sleep 3`,
  `ss -tlnp | grep 3001`,
  `curl -s -o /dev/null -w "backend:3001/studio/ -> %{http_code}\\n" http://localhost:3001/studio/`,
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
