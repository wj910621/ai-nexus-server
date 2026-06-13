const { Client } = require('ssh2');

const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 系统信息
  'echo "===== 系统信息 ====="',
  'uname -a',
  'cat /etc/os-release | head -3',
  'uptime',
  'df -h /',
  'free -h',
  
  // Nginx 状态
  'echo "===== Nginx ====="',
  'nginx -v 2>&1 || echo "nginx not installed"',
  'ls -la /etc/nginx/conf.d/',
  'nginx -t 2>&1',
  'ss -tlnp | grep -E "(80|443)"',
  
  // PM2 状态
  'echo "===== PM2 ====="',
  'pm2 list 2>&1 || echo "pm2 not installed"',
  
  // 后端服务
  'echo "===== 后端服务 ====="',
  'ss -tlnp | grep -E "(3001)"',
  'curl -s -o /dev/null -w "localhost:3001 -> %{http_code}\n" http://localhost:3001/',
  'curl -s -o /dev/null -w "localhost:3001/studio/ -> %{http_code}\n" http://localhost:3001/studio/',
  
  // 前端文件
  'echo "===== 前端文件 ====="',
  'ls -la /home/admin/nexus-studio/',
  'ls -la /home/admin/ai-nexus/',
  
  // 防火墙
  'echo "===== 防火墙 ====="',
  'systemctl status firewalld 2>&1 | head -5',
  'iptables -L INPUT -n --line-numbers 2>&1 | head -20',
  
  // DNS 检查
  'echo "===== DNS ====="',
  'nslookup j3trisheng.com 2>&1 || echo "nslookup failed"',
  'dig j3trisheng.com +short 2>&1 || echo "dig failed"',
  
  // 证书
  'echo "===== SSL ====="',
  'ls -la /etc/letsencrypt/live/j3trisheng.com/ 2>&1 || echo "no letsencrypt cert"',
  'certbot certificates 2>&1 | head -10 || echo "certbot not found"',
];

const conn = new Client();

conn.on('ready', () => {
  console.log('✅ SSH 连接成功！\n');
  runCommands(0);
});

conn.on('error', (err) => {
  console.error('❌ 连接错误:', err.message);
  process.exit(1);
});

function runCommands(idx) {
  if (idx >= commands.length) {
    console.log('\n✅ 诊断完成');
    conn.end();
    return;
  }
  
  const cmd = commands[idx];
  conn.exec(cmd, (err, stream) => {
    if (err) {
      console.log(`[ERR] ${cmd.substring(0,60)}: ${err.message}`);
      runCommands(idx + 1);
      return;
    }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('close', () => {
      if (out.trim()) console.log(out);
      runCommands(idx + 1);
    });
  });
}

conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
