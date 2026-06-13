const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查服务器上实际部署的 index.html ====="`,
  `head -25 /home/admin/nexus-studio/main-index.html`,
  `echo "===== 检查 API_BASE ====="`,
  `grep -A 5 "const API_BASE" /home/admin/nexus-studio/main-index.html | head -8`,
  `echo "===== 检查侧边栏导航 ====="`,
  `grep -n "sidebar-link" /home/admin/nexus-studio/main-index.html | head -25`,
  `echo "===== 检查模型数量描述 ====="`,
  `grep -n "500\|30\|模型" /home/admin/nexus-studio/main-index.html | grep -E "(接入|模型|500|30)" | head -10`,
  `echo "===== 检查 API Key 描述 ====="`,
  `grep -A 2 "API Key 管理" /home/admin/nexus-studio/main-index.html | head -5`,
  `echo "===== 检查是否有 landing 页面 ====="`,
  `ls -la /home/admin/nexus-studio/landing.html 2>&1`,
  `echo "===== 检查 Nginx 配置 ====="`,
  `cat /etc/nginx/conf.d/j3trisheng.conf | head -20`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { console.log('Done'); conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
