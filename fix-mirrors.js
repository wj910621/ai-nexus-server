const { Client } = require('ssh2');

const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 修复 CentOS 8 仓库源（EOL fallback to vault）
  `echo "===== 修复 CentOS 8 仓库 ====="`,
  `sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-*`,
  `sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*`,
  `yum clean all 2>&1 | tail -2`,
  `yum makecache 2>&1 | tail -3`,
  
  // 安装 Nginx
  `echo "===== 安装 Nginx ====="`,
  `yum install -y nginx 2>&1 | tail -5`,
  
  // 验证安装
  `echo "===== 验证 Nginx ====="`,
  `nginx -v 2>&1`,
  `ss -tlnp | grep -E "(80|443)"`,
  
  // 测试配置
  `echo "===== 测试 Nginx 配置 ====="`,
  `nginx -t 2>&1`,
  
  // 启动 Nginx
  `echo "===== 启动 Nginx ====="`,
  `nginx 2>&1; echo "exit: $?"`,
  `systemctl enable nginx 2>&1`,
  
  // 检查端口
  `echo "===== 检查 Nginx 端口 ====="`,
  `ss -tlnp | grep -E "(80|443)"`,
  
  // 测试
  `echo "===== 本地测试 ====="`,
  `curl -s -o /dev/null -w "localhost:80 -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "120.79.17.184:80 -> %{http_code}\n" http://120.79.17.184/`,
  `curl -s -o /dev/null -w "120.79.17.184:80/studio/ -> %{http_code}\n" http://120.79.17.184/studio/`,
];

console.log('正在连接服务器修复 CentOS 8 仓库并安装 Nginx...');
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
    console.log('\n✅ 完成！');
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
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => {
      if (out.trim()) console.log(out);
      runCommands(idx + 1);
    });
  });
}

conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
