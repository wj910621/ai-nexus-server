const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `echo "===== 目录权限 ====="`,
  `ls -la /home/admin/nexus-studio/`,
  `ls -la /home/admin/`,
  `stat /home/admin/nexus-studio/index.html`,
  
  `echo "===== Nginx 错误日志 ====="`,
  `tail -20 /var/log/nginx/error.log 2>&1`,
  
  `echo "===== Nginx 用户 ====="`,
  `grep '^user' /etc/nginx/nginx.conf`,
  `id nginx 2>&1`,
  
  `echo "===== 修复权限 ====="`,
  `chown -R nginx:nginx /home/admin/nexus-studio/ 2>&1; echo "chown done"`,
  `chmod -R 755 /home/admin/nexus-studio/ 2>&1; echo "chmod done"`,
  
  `echo "===== 重新测试 ====="`,
  `curl -s -o /dev/null -w "local:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "IP:80/studio/ -> %{http_code}\n" http://120.79.17.184/studio/`,
  
  `echo "===== 详细调试 ====="`,
  `curl -s -D - http://localhost/studio/ 2>&1 | head -20`,
  
  `echo "===== Nginx 访问日志 ====="`,
  `tail -10 /var/log/nginx/access.log 2>&1`,
  
  `echo "===== 也测试直接访问 3001 ====="`,
  `curl -s -D - http://localhost:3001/studio/ 2>&1 | head -20`,
];

console.log('排查 /studio/ 404 问题...');
const conn = new Client();
conn.on('ready', () => { console.log('✅ SSH 连接成功\n'); runCommands(0); });
conn.on('error', (err) => { console.error('❌ 连接错误:', err.message); process.exit(1); });
function runCommands(idx) {
  if (idx >= commands.length) { console.log('\n✅ 完成'); conn.end(); return; }
  const cmd = commands[idx];
  conn.exec(cmd, (err, stream) => {
    if (err) { console.log(`[ERR]: ${err.message}`); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => { if (out.trim()) console.log(out.trim()); runCommands(idx + 1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
