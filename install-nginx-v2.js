const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

const commands = [
  // 检查网络连通性
  `echo "===== 网络连通性 ====="`,
  `curl -sI --connect-timeout 5 https://mirrors.aliyun.com/centos-vault/8.5.2111/ | head -3`,
  `curl -sI --connect-timeout 5 https://nginx.org/packages/centos/8/ | head -3`,
  
  // 修复 CentOS 8 仓库 - 使用阿里云 vault 镜像
  `echo "===== 修复 YUM 仓库 ====="`,
  `cat > /etc/yum.repos.d/CentOS-Base.repo << 'REPO'
[baseos]
name=CentOS Linux $releasever - Base
baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111/BaseOS/x86_64/os/
gpgcheck=1
enabled=1
gpgkey=https://mirrors.aliyun.com/centos-vault/8.5.2111/BaseOS/x86_64/os/RPM-GPG-KEY-CentOS-8

[appstream]
name=CentOS Linux $releasever - AppStream
baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111/AppStream/x86_64/os/
gpgcheck=1
enabled=1
gpgkey=https://mirrors.aliyun.com/centos-vault/8.5.2111/AppStream/x86_64/os/RPM-GPG-KEY-CentOS-8

[extras]
name=CentOS Linux $releasever - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111/extras/x86_64/os/
gpgcheck=1
enabled=1
gpgkey=https://mirrors.aliyun.com/centos-vault/8.5.2111/extras/x86_64/os/RPM-GPG-KEY-CentOS-8

[epel]
name=Extra Packages for Enterprise Linux $releasever - $basearch
baseurl=https://mirrors.aliyun.com/epel/8/Everything/x86_64/
gpgcheck=0
enabled=1
REPO`,
  `echo "repo 写入完成"`,
  
  // 清理缓存
  `yum clean all 2>&1 | tail -2`,
  
  // 安装 nginx
  `echo "===== 安装 nginx ====="`,
  `yum install -y nginx --disablerepo=* --enablerepo=appstream,baseos,extras 2>&1 | tail -10`,
  
  // 如果失败尝试 dnf
  `which nginx 2>&1 || (dnf install -y nginx 2>&1 | tail -10)`,
  
  // 最终检查
  `echo "===== 最终检查 ====="`,
  `which nginx && nginx -v 2>&1 || echo "nginx not installed"`,
];

console.log('安装 Nginx...');
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
