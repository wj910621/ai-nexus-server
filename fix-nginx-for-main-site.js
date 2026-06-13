const { Client } = require('ssh2');
const conn = new Client();

const cmds = [
  // 删除旧的 default-trizen.conf
  `rm -f /etc/nginx/conf.d/default-trizen.conf`,
  
  // 写入新的配置
  `cat > /etc/nginx/conf.d/j3trisheng.conf << 'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name j3trisheng.com www.j3trisheng.com _;

    # 主站前端 - SPA，所有路径指向 main-index.html
    root /home/admin/nexus-studio/;
    index main-index.html;

    # 静态资源直接提供
    location /css/ { }
    location /js/ { }
    location /download/ { }
    location /icons/ { }
    
    # /studio/ → TriGen Desktop（新 UI）
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
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
        proxy_send_timeout 300s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # SPA 路由：非文件路径回退到 main-index.html
    location / {
        try_files $uri $uri/ /main-index.html;
    }
}
NGINX`,
  `echo "Config written"`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  `echo "===== 验证 ====="`,
  `curl -4 -s -o /dev/null -w "root -> %{http_code}\\n" http://127.0.0.1/`,
  `curl -4 -s -o /dev/null -w "studio -> %{http_code}\\n" http://127.0.0.1/studio/`,
  `curl -4 -s -o /dev/null -w "main-index.html -> %{http_code}\\n" http://127.0.0.1/main-index.html`,
  `echo "===== 旧文件清理 ====="`,
  `rm -f /home/admin/nexus-studio/test-ui.html /home/admin/nexus-studio/test-ui-v2.html`,
  `ls -la /home/admin/nexus-studio/`,
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
