const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const nginxConfig = `server {
    listen 80;
    server_name j3trisheng.com www.j3trisheng.com _;

    # Nexus Studio PWA 前端
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
        proxy_cache off;
        proxy_read_timeout 120s;
    }

    # v1 API 代理 (OpenAI 兼容)
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

    # 下载路径
    location /download/ {
        alias /home/admin/nexus-studio/download/;
    }

    # 根路径 -> 重定向到 /studio/
    location = / {
        return 302 /studio/;
    }

    # 其他请求交给后端
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
`;

const commands = [
  // 写入配置
  `echo "===== 写入 Nginx 配置 ====="`,
  `cat > /etc/nginx/conf.d/j3trisheng.conf << 'NGINX_EOF'
${nginxConfig}
NGINX_EOF`,
  `echo "配置已写入"`,
  `ls -la /etc/nginx/conf.d/`,
  
  // 测试配置
  `echo "===== 测试 Nginx 配置 ====="`,
  `nginx -t 2>&1`,
  
  // 重载 Nginx
  `echo "===== 重载 Nginx ====="`,
  `nginx -s reload 2>&1`,
  
  // 验证
  `echo "===== 验证 ====="`,
  `curl -s -o /dev/null -w "localhost:80/ -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost:80/studio/ -> %{http_code}\n" http://localhost/studio/`,
  `curl -s -o /dev/null -w "IP:80/studio/ -> %{http_code}\n" http://120.79.17.184/studio/`,
  
  // 检查 PM2 进程问题
  `echo "===== 检查 3001 端口占用 ====="`,
  `lsof -i :3001 2>&1 || ss -tlnp | grep 3001`,
  `echo "PM2 状态: " && pm2 list 2>&1 | grep nexus`,
];

console.log('写入 Nginx 配置...');
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
