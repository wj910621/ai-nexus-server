const { Client } = require('ssh2');

const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

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
  // 1. 安装 Nginx
  `echo "===== 1. 安装 Nginx ====="`,
  `yum install -y nginx 2>&1 | tail -5`,
  
  // 2. 写入配置文件
  `echo "===== 2. 写入 Nginx 配置 ====="`,
  `cat > /etc/nginx/conf.d/j3trisheng.conf << 'NGINX_EOF'
${nginxConfig}
NGINX_EOF`,
  `echo "配置文件已写入"`,
  
  // 3. 测试 Nginx 配置
  `echo "===== 3. 测试 Nginx 配置 ====="`,
  `nginx -t 2>&1`,
  
  // 4. 启动 Nginx
  `echo "===== 4. 启动 Nginx ====="`,
  `nginx 2>&1; echo "Nginx 启动完成"`,
  `systemctl enable nginx 2>&1`,
  
  // 5. 检查 Nginx 是否在监听
  `echo "===== 5. 检查端口 ====="`,
  `ss -tlnp | grep -E "(80|443)"`,
  
  // 6. 检查后端健康
  `echo "===== 6. 后端健康检查 ====="`,
  `curl -s -o /dev/null -w "localhost:3001/studio/: %{http_code}\n" http://localhost:3001/studio/`,
  `curl -s -o /dev/null -w "localhost:3001/: %{http_code}\n" http://localhost:3001/`,
  
  // 7. 本地回环测试 Nginx
  `echo "===== 7. Nginx 回环测试 ====="`,
  `curl -s -o /dev/null -w "localhost -> %{http_code}\n" http://localhost/`,
  `curl -s -o /dev/null -w "localhost/studio/ -> %{http_code}\n" http://localhost/studio/`,
  
  // 8. 修复 PM2
  `echo "===== 8. PM2 状态 ====="`,
  `pm2 restart nexus-hub 2>&1 | tail -5`,
  `pm2 save 2>&1`,
  
  // 9. 检查服务器是否可以访问自己
  `echo "===== 9. 公网 IP 自检 ====="`,
  `curl -s -o /dev/null -w "http://120.79.17.184/ -> %{http_code}\n" http://120.79.17.184/`,
  `curl -s -o /dev/null -w "http://120.79.17.184/studio/ -> %{http_code}\n" http://120.79.17.184/studio/`,
];

console.log('正在连接服务器...');
const conn = new Client();
conn.on('ready', () => {
  console.log('✅ SSH 连接成功！\n');
  runCommands(0);
});
conn.on('error', (err) => {
  console.error('❌ 连接错误:', err.message);
  process.exit(1);
});

function runCommands(idx) {
  if (idx >= commands.length) {
    console.log('\n✅ 服务器设置完成！');
    console.log('\n下一步建议:');
    console.log('1. 检查 Cloudflare Dashboard 确认 DNS 代理模式（橙色云 = 已代理）');
    console.log('2. 如果 Cloudflare 是代理模式，访问 https://j3trisheng.com 测试');
    console.log('3. 如需 HTTPS，配置 Cloudflare Origin Certificate 或 Let\'s Encrypt');
    conn.end();
    return;
  }
  const cmd = commands[idx];
  conn.exec(cmd, (err, stream) => {
    if (err) {
      console.log(`[ERR] ${cmd.substring(0,60)}: ${err.message}`);
      runCommands(idx + 1);
      return;
    }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('close', () => {
      if (out.trim()) console.log(out);
      runCommands(idx + 1);
    });
  });
}

conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
