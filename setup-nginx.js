const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

conn.on('ready', () => {
  console.log('已连接，更新 Nginx 配置...');

  const nginxConfig = `server {
    listen 80;
    server_name j3trisheng.com www.j3trisheng.com _;

    # 前端静态文件（Nexus Studio PWA）
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html index_app.html;
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

    # 根路径指向主页（也可以重定向到 /studio/）
    location = / {
        return 302 /studio/;
    }

    # 其他所有请求交给后端
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

  conn.exec('cat > /etc/nginx/conf.d/j3trisheng.conf << \'ENDSCRIPT\'\n' + nginxConfig + '\nENDSCRIPT', (err, stream) => {
    if (err) { console.log('write error:', err); conn.end(); return; }
    stream.on('close', () => {
      console.log('Nginx 配置文件已写入');

      // 测试 Nginx 配置
      conn.exec('nginx -t 2>&1', (err, stream) => {
        if (err) { console.log('test error:', err); conn.end(); return; }
        stream.on('data', d => process.stdout.write(d));
        stream.on('close', () => {
          console.log('\n');

          // 重载 Nginx
          conn.exec('nginx -s reload 2>&1', (err, stream) => {
            if (err) { console.log('reload error:', err); conn.end(); return; }
            stream.on('data', d => process.stdout.write(d));
            stream.on('close', () => {
              console.log('\n✅ Nginx 重载完成');
              conn.end();
            });
          });
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
