const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  // 修复下载目录权限
  `chmod 755 /home/admin/nexus-studio/download/ && chown -R nginx:nginx /home/admin/nexus-studio/download/ && echo "download权限已修复"`,
  
  // 修复 Nginx 配置，添加下载目录索引
  `cat > /etc/nginx/conf.d/j3trisheng.conf << 'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name j3trisheng.com www.j3trisheng.com _;

    root /home/admin/nexus-studio/;
    index landing.html;

    # 欢迎页
    location = / {
        try_files /landing.html =404;
    }

    # /studio/ → TriGen Desktop
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        try_files $uri $uri/ =404;
    }

    # 下载目录 - 允许列出文件
    location /download/ {
        alias /home/admin/nexus-studio/download/;
        autoindex on;
        autoindex_exact_size off;
        autoindex_localtime on;
    }

    # 静态资源
    location /css/ { }
    location /js/ { }
    location /icons/ { }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # 主站 SPA 路由
    location / {
        try_files $uri $uri/ /landing.html;
    }
}
NGINX`,
  `echo "Nginx配置已更新"`,
  `nginx -t 2>&1 && nginx -s reload 2>&1`,
  `echo "===== 测试下载页 ====="`,
  `curl -s -o /dev/null -w "下载页: %{http_code}\n" http://127.0.0.1/download/`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('错误:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { console.log('完成'); conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('错误:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
