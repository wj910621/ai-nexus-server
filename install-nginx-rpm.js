const { Client } = require('ssh2');

const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 直接通过 nginx.org 官方 RPM 安装（不依赖 yum 仓库）
  `echo "===== 下载并安装 nginx ====="`,
  `cd /tmp && curl -sL -o nginx.rpm https://nginx.org/packages/centos/8/x86_64/RPMS/nginx-1.24.0-1.el8.ngx.x86_64.rpm 2>&1 && echo "下载完成" || echo "下载失败"`,
  
  // 如果下载失败，尝试其他版本
  `ls -la /tmp/nginx.rpm 2>&1`,
  
  // 安装
  `echo "===== 安装 nginx RPM ====="`,
  `rpm -ivh /tmp/nginx.rpm 2>&1 || yum install -y /tmp/nginx.rpm 2>&1`,
  
  // 验证
  `nginx -v 2>&1`,
  
  // 确认之前的配置文件存在
  `echo "===== 确认 Nginx 配置 ====="`,
  `ls -la /etc/nginx/conf.d/`,
  `cat /etc/nginx/conf.d/j3trisheng.conf | head -5`,
  
  // 测试配置
  `nginx -t 2>&1`,
  
  // 启动
  `nginx 2>&1; echo "exit: $?"`,
  `systemctl enable nginx 2>&1`,
  
  // 检查端口
  `echo "===== 端口检查 ====="`,
  `ss -tlnp | grep -E "(80|443)"`,
  
  // 本地测试
  `echo "===== 本地测试 ====="`,
  `curl -s -o /dev/null -w "localhost:80 -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
];

console.log('通过 nginx.org RPM 安装 Nginx...');
const conn = new Client();
conn.on('ready', () => {
  console.log('✅ SSH 连接成功\n');
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
    if (err) { console.log(`[ERR]: ${err.message}`); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => {
      if (out.trim()) console.log(out.trim());
      runCommands(idx + 1);
    });
  });
}

conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
