const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const cmds = [
  `echo "===== PM2 开机自启 ====="`,
  `env PATH=$PATH:/usr/bin pm2 startup systemd -u root --hp /root 2>&1 | tail -5`,
  `pm2 save --force 2>&1`,
  `echo "===== 设置 PM2 日志清理 ====="`,
  `pm2 install pm2-logrotate 2>&1 | tail -3`,
  `echo "===== Nginx 最终状态 ====="`,
  `systemctl status nginx 2>&1 | head -5`,
  `ss -tlnp | grep -E "(80|443|3001)"`,
  `echo "===== 磁盘和内存 ====="`,
  `df -h /`,
  `free -h`,
  `echo "===== 从外网检查 ====="`,
  `curl -s -o /dev/null -w "公网IP:80 -> %{http_code}\\n" -m 10 http://120.79.17.184/ 2>&1`,
  `curl -s -o /dev/null -w "j3trisheng.com:80 -> %{http_code}\\n" -m 10 http://j3trisheng.com/ 2>&1`,
  `echo "===== 阿里云安全组提示 ====="`,
  `echo "请在阿里云 ECS 控制台安全组中确保以下端口已开放:"`,
  `echo "  - 80 (HTTP)"`,
  `echo "  - 443 (HTTPS, 配置 SSL 后)"`,
  `echo "  - 22 (SSH)"`,
];

const { Client: SshClient } = require('ssh2');
const conn = new SshClient();
conn.on('ready', () => { console.log('✅ SSH 连接成功\n'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { console.log('\n✅ 服务器配置完成'); conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
