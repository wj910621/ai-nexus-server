const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

// SSL 配置（Cloudflare Origin CA 证书）
// 使用方法：
// 1. 在 Cloudflare Dashboard → SSL/TLS → Origin Server → Create Certificate
// 2. 域名: j3trisheng.com, *.j3trisheng.com
// 3. 将生成的证书内容保存到 /etc/nginx/ssl/origin.pem
// 4. 将生成的私钥内容保存到 /etc/nginx/ssl/origin.key
// 5. 运行此脚本完成 Nginx SSL 配置

const sslNginxConfig = `server {
    listen 443 ssl http2;
    server_name j3trisheng.com www.j3trisheng.com;

    ssl_certificate /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Nexus Studio PWA 前端
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
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
        proxy_cache off;
        proxy_read_timeout 120s;
    }
}

# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name j3trisheng.com www.j3trisheng.com;
    return 301 https://$server_name$request_uri;
}
`;

const commands = [
  `echo "===== 创建 SSL 目录 ====="`,
  `mkdir -p /etc/nginx/ssl`,
  
  // 写入 SSL 配置（证书文件需要用户手动上传）
  `echo "===== 写入 SSL Nginx 配置 ====="`,
  `cat > /etc/nginx/conf.d/j3trisheng-ssl.conf << 'NGINX_EOF'
${sslNginxConfig}
NGINX_EOF`,
  `echo "SSL 配置已写入 /etc/nginx/conf.d/j3trisheng-ssl.conf"`,
  
  `echo "===== 当前 Nginx 配置清单 ====="`,
  `ls -la /etc/nginx/conf.d/`,
  
  `echo "===== 更新 HTTP 配置（移除 _ 避免冲突） ====="`,
  `cat > /etc/nginx/conf.d/j3trisheng.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name j3trisheng.com www.j3trisheng.com;

    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
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
        proxy_cache off;
        proxy_read_timeout 120s;
    }
}
NGINX_EOF`,
  `echo "HTTP 配置已更新"`,
  
  `echo "===== 测试配置 ====="`,
  `nginx -t 2>&1`,
  
  `echo "===== 重载 Nginx ====="`,
  `nginx -s reload 2>&1`,
  
  `echo "===== 验证 ====="`,
  `curl -s -o /dev/null -w "HTTP:80/studio/ -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
];

const conn = new Client();
conn.on('ready', () => { console.log('✅ SSH 连接成功\n'); runCommands(0); });
conn.on('error', (err) => { console.error('Error:', err.message); process.exit(1); });
function runCommands(idx) {
  if (idx >= commands.length) { console.log('\n✅ SSL 准备完成'); conn.end(); return; }
  conn.exec(commands[idx], (err, stream) => {
    if (err) { console.log('ERR:', err.message); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => { if (out.trim()) console.log(out.trim()); runCommands(idx + 1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
