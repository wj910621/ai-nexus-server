const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  // 检查是否有 cloudflare 相关文件
  `echo "===== 搜索 Cloudflare 相关文件 ====="`,
  `find /root /home /etc -name "*cloudflare*" -o -name "*cloudflared*" -o -name "*tunnel*" 2>/dev/null`,
  `find /root /home /etc -name "*.json" 2>/dev/null | grep -i cloud`,
  `echo "===== 检查 PM2 历史进程 ====="`,
  `pm2 list 2>&1`,
  `ls /root/.pm2/dump.pm2 2>&1 && cat /root/.pm2/dump.pm2 2>&1 | head -20`,
  `echo "===== 删除原有 default_server ====="`,
  `sed -i 's/listen       80 default_server;/listen       80;/' /etc/nginx/nginx.conf`,
  `sed -i 's/listen       \\[::\\]:80 default_server;/listen       [::]:80;/' /etc/nginx/nginx.conf`,
  `echo "===== 修改默认配置 ====="`,
  `cat > /etc/nginx/conf.d/default-trizen.conf << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    # 双入口：IP 直接访问时跳转 /studio/
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 120s;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 120s;
    }

    location /download/ {
        alias /home/admin/nexus-studio/download/;
    }

    location = / {
        return 302 /studio/;
    }

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 120s;
    }
}
EOF`,
  `echo "配置已写入"`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  `echo "===== IP 直接访问测试 ====="`,
  `curl -s -o /dev/null -w "127.0.0.1:80/ -> %{http_code}\\n" http://127.0.0.1/`,
  `curl -s -o /dev/null -w "127.0.0.1:80/studio/ -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `curl -s -o /dev/null -w "域名访问:80/studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `echo "===== 检查 j3trisheng.com 是否使用了 Tunnel ====="`,
  `curl -v -s -o /dev/null -w "\\nhttp_code: %{http_code}\\n" -m 10 https://j3trisheng.com 2>&1 | head -15`,
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
