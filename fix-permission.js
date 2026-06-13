const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `echo "===== 父目录权限 ====="`,
  `ls -la /home/`,
  `stat /home/admin/`,
  
  `echo "===== 修复父目录权限 ====="`,
  `chmod o+x /home/admin/`,
  
  `echo "===== 验证权限 ====="`,
  `sudo -u nginx ls /home/admin/nexus-studio/ 2>&1 | head -5`,
  
  `echo "===== 测试 ====="`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\\n" http://localhost/studio/`,
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
