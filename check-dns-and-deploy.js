const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 完整 DNS 记录 ====="`,
  `dig j3trisheng.com ANY +short 2>&1`,
  `dig j3trisheng.com CNAME +short 2>&1`,
  `dig j3trisheng.com A +short 2>&1`,
  `echo "===== 检查 www 子域名 ====="`,
  `dig www.j3trisheng.com A +short 2>&1`,
  `echo "===== 测试 Cloudflare 代理连通性 ====="`,
  `curl -v -s -o /dev/null -w "\\nhttp_code: %{http_code}\\n" --connect-timeout 10 http://j3trisheng.com 2>&1`,
  `echo "===== 查看 Nginx 访问日志 ====="`,
  `tail -20 /var/log/nginx/access.log 2>&1`,
  `echo "===== 部署前端到服务器 ====="`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { console.log('完成'); conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
