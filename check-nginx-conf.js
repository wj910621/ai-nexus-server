const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 检查默认 nginx.conf
  `echo "===== 默认 nginx.conf ====="`,
  `cat /etc/nginx/nginx.conf`,
  
  // 用 Host 头测试（确认配置本身正确）
  `echo "===== Host 头测试 ====="`,
  `curl -s -o /dev/null -w "j3trisheng.com/studio/ -> %{http_code}\n" -H "Host: j3trisheng.com" http://localhost/studio/`,
  `curl -s -o /dev/null -w "j3trisheng.com/ -> %{http_code}\n" -H "Host: j3trisheng.com" http://localhost/`,
];

console.log('检查 nginx.conf 并测试...');
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
