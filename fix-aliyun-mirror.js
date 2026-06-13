const { Client } = require('ssh2');

const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  // 使用阿里云镜像
  `echo "===== 切换到阿里云 CentOS 8 镜像 ====="`,
  `sed -e 's|^mirrorlist=|#mirrorlist=|g' \\
      -e 's|^#baseurl=http://mirror.centos.org/\\$contentdir|baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111|g' \\
      -i.bak /etc/yum.repos.d/CentOS-Base.repo`,
  `sed -e 's|^mirrorlist=|#mirrorlist=|g' \\
      -e 's|^#baseurl=http://mirror.centos.org/\\$contentdir|baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111|g' \\
      -i /etc/yum.repos.d/CentOS-AppStream.repo 2>/dev/null || true`,
  `sed -e 's|^mirrorlist=|#mirrorlist=|g' \\
      -e 's|^#baseurl=http://mirror.centos.org/\\$contentdir|baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111|g' \\
      -i /etc/yum.repos.d/CentOS-PowerTools.repo 2>/dev/null || true`,
  `yum clean all 2>&1 | tail -2`,
  `yum makecache 2>&1 | tail -5`,

  // 安装 Nginx
  `echo "===== 安装 Nginx ====="`,
  `yum install -y nginx 2>&1 | tail -5`,
  
  // 验证
  `echo "===== 验证 Nginx ====="`,
  `nginx -v 2>&1`,
  
  // 之前已写入配置文件，确认存在
  `echo "===== 确认配置 ====="`,
  `ls -la /etc/nginx/conf.d/`,
  `cat /etc/nginx/conf.d/j3trisheng.conf | head -20`,
  
  // 测试配置
  `echo "===== 测试 Nginx 配置 ====="`,
  `nginx -t 2>&1`,
  
  // 启动 Nginx
  `echo "===== 启动 Nginx ====="`,
  `nginx 2>&1; echo "exit code: $?"`,
  `systemctl enable nginx 2>&1`,
  
  // 检查端口
  `echo "===== 检查 Nginx 端口 ====="`,
  `ss -tlnp | grep -E "(80|443)"`,
  
  // 测试
  `echo "===== 本地测试 ====="`,
  `curl -s -o /dev/null -w "localhost:80 -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "IP:80 -> %{http_code}\n" http://120.79.17.184/`,
];

console.log('切换到阿里云镜像 + 安装 Nginx...');
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
    if (err) { console.log(`[ERR]: ${err.message}`); runCommands(idx + 1); return; }
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
