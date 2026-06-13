const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 禁用 SSL 配置（证书未安装）
  `echo "===== 禁用 SSL 配置 ====="`,
  `mv /etc/nginx/conf.d/j3trisheng-ssl.conf /etc/nginx/conf.d/j3trisheng-ssl.conf.disabled`,
  `echo "SSL 配置已禁用（如需启用：重命名回 j3trisheng-ssl.conf 即可）"`,
  
  // 测试配置
  `echo "===== 测试并重载 ====="`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  
  // 最终验证
  `echo "===== 最终 Nginx 配置列表 ====="`,
  `ls -la /etc/nginx/conf.d/`,
  
  `echo "===== 最终验证 ====="`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/ -> %{http_code}\\n" http://127.0.0.1/`,
  `curl -4 -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `curl -s -H "Host: j3trisheng.com" -o /dev/null -w "j3trisheng.com:80/studio/ -> %{http_code}\\n" http://localhost/studio/`,
  `curl -s -H "Host: www.j3trisheng.com" -o /dev/null -w "www.j3trisheng.com:80/studio/ -> %{http_code}\\n" http://localhost/studio/`,
  
  `echo "===== 从外部测试 ====="`,
  `curl -s -o /dev/null -w "http://j3trisheng.com -> %{http_code}\\n" -m 10 http://j3trisheng.com 2>&1`,
];

const conn = new Client();
conn.on('ready', () => { console.log('✅ SSH 连接成功\n'); runCommands(0); });
conn.on('error', (err) => { console.error('Error:', err.message); process.exit(1); });
function runCommands(idx) {
  if (idx >= commands.length) { console.log('\n✅ 最终配置完成'); conn.end(); return; }
  conn.exec(commands[idx], (err, stream) => {
    if (err) { console.log('ERR:', err.message); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => { if (out.trim()) console.log(out.trim()); runCommands(idx + 1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
