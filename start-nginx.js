const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 确认配置
  `echo "===== 确认配置文件 ====="`,
  `ls -la /etc/nginx/conf.d/`,
  `cat /etc/nginx/conf.d/j3trisheng.conf | head -15`,
  
  // 测试配置
  `echo "===== 测试 Nginx 配置 ====="`,
  `nginx -t 2>&1`,
  
  // 如果有报错，修正配置
  `echo "===== 检查默认配置冲突 ====="`,
  `ls -la /etc/nginx/conf.d/default.conf 2>&1`,
  `mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.disabled 2>/dev/null; echo "done"`,
  `nginx -t 2>&1`,
  
  // 启动 Nginx
  `echo "===== 启动 Nginx ====="`,
  `nginx 2>&1; echo "exit: $?"`,
  `systemctl enable nginx 2>&1`,
  
  // 端口检查
  `echo "===== 端口检查 ====="`,
  `ss -tlnp | grep -E "(80|443)"`,
  
  // 本地测试
  `echo "===== 本地测试 ====="`,
  `curl -s -o /dev/null -w "localhost:80 -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "IP:80 -> %{http_code}\n" http://120.79.17.184/`,
  `curl -s -o /dev/null -w "IP:80/studio/ -> %{http_code}\n" http://120.79.17.184/studio/`,
  `curl -s -o /dev/null -w "IP:3001/studio/ -> %{http_code}\n" http://120.79.17.184:3001/studio/`,
  
  // 测试 PM2
  `echo "===== PM2 状态 ====="`,
  `pm2 list 2>&1 | head -10`,
  `pm2 logs nexus-hub --lines 10 --nostream 2>&1 | tail -10`,
];

console.log('启动 Nginx 并验证...');
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
