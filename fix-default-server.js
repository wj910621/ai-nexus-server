const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 用正确 Host 头测试
  `echo "===== 用 Host 头测试 ====="`,
  `curl -s -o /dev/null -w "j3trisheng.com:80/ -> %{http_code}\n" -H "Host: j3trisheng.com" http://localhost/`,
  `curl -s -o /dev/null -w "j3trisheng.com:80/studio/ -> %{http_code}\n" -H "Host: j3trisheng.com" http://localhost/studio/`,
  
  // 修复配置：使用 default_server
  `echo "===== 更新 Nginx 配置为 default_server ====="`,
  `sed -i 's/listen 80;/listen 80 default_server;/' /etc/nginx/conf.d/j3trisheng.conf`,
  `cat /etc/nginx/conf.d/j3trisheng.conf | head -5`,
  
  // 删除默认配置中的 server_name _ 
  `echo "===== 修改默认 nginx.conf 移除冲突 ====="`,
  `grep -n "default_server" /etc/nginx/nginx.conf`,
  
  // 测试配置
  `echo "===== 测试并重载 ====="`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  
  // 验证
  `echo "===== 再次验证 ====="`,
  `curl -s -o /dev/null -w "localhost:80/ -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "IP:80/studio/ -> %{http_code}\n" http://120.79.17.184/studio/`,
  `curl -s -o /dev/null -w "Host=j3trisheng.com:80/studio/ -> %{http_code}\n" -H "Host: j3trisheng.com" http://localhost/studio/`,
  `curl -s -o /dev/null -w "Host=www.j3trisheng.com:80/studio/ -> %{http_code}\n" -H "Host: www.j3trisheng.com" http://localhost/studio/`,
];

console.log('修复 Nginx 默认服务器配置...');
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
