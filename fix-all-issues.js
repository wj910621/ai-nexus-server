const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== 检查 cloudflared ====="`,
  `which cloudflared 2>/dev/null && cloudflared version || echo "cloudflared NOT installed"`,
  `systemctl status cloudflared 2>&1 || true`,
  `ls /etc/cloudflared/ 2>&1 || echo "no cloudflared dir"`,
  `echo "===== 检查 DNS 记录 ====="`,
  `nslookup j3trisheng.com 2>&1`,
  `dig j3trisheng.com +short 2>&1`,
  `echo "===== 检查端口监听 ====="`,
  `ss -tlnp`,
  `echo "===== 修复默认 server 块 ====="`,
  `cat > /etc/nginx/conf.d/default-trizen.conf << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    # 重定向到 /studio/
    location = / {
        return 302 /studio/;
    }

    # 所有请求交给 /studio/
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location / {
        try_files $uri $uri/ /studio/;
    }
}
EOF`,
  `echo "默认 server 配置已写入"`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  `echo "===== 默认 IP 测试 ====="`,
  `curl -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "127.0.0.1:80/ -> %{http_code}\\n" http://127.0.0.1/`,
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
