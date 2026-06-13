const { Client } = require('ssh2');
const fs = require('fs');
const conn = new Client();

// 从源文件读取
const mainIndex = fs.readFileSync('G:/大模型聚合网站/index.html'); // 主站首页 548KB
const landingHtml = fs.readFileSync('G:/大模型聚合网站/landing.html');

conn.on('ready', () => {
  console.log('✅ 连接成功，上传主站文件...');
  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP err:', err); process.exit(1); }
    
    // 上传主站首页到根路径
    sftp.fastPut('G:/大模型聚合网站/index.html', '/home/admin/nexus-studio/main-index.html', (err) => {
      if (err) { console.error('Upload main-index error:', err); process.exit(1); }
      console.log('✅ main-index.html 上传完成');
      
      // 上传 landing.html
      sftp.fastPut('G:/大模型聚合网站/landing.html', '/home/admin/nexus-studio/landing.html', (err2) => {
        if (err2) { console.error('Upload landing error:', err2); process.exit(1); }
        console.log('✅ landing.html 上传完成');
        
        // 修改 Nginx 配置：根路径 → 主站 index.html
        conn.exec('cat > /etc/nginx/conf.d/j3trisheng.conf << \'EOF\'\nserver {\n    listen 80;\n    listen [::]:80;\n    server_name j3trisheng.com www.j3trisheng.com;\n\n    # 根路径 → 主站（TriGen 品牌官网首页）\n    location = / {\n        root /home/admin/nexus-studio/;\n        try_files /main-index.html /index.html =404;\n    }\n\n    # /studio/ → TriGen Desktop 前端\n    location /studio/ {\n        alias /home/admin/nexus-studio/;\n        index index.html;\n        expires 0;\n        add_header Cache-Control "no-cache, no-store, must-revalidate";\n    }\n\n    location /api/ {\n        proxy_pass http://127.0.0.1:3001;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_buffer_size 128k;\n        proxy_buffers 4 256k;\n        proxy_busy_buffers_size 256k;\n        proxy_read_timeout 300s;\n        proxy_send_timeout 300s;\n    }\n\n    location /v1/ {\n        proxy_pass http://127.0.0.1:3001;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_buffer_size 128k;\n        proxy_buffers 4 256k;\n        proxy_busy_buffers_size 256k;\n        proxy_read_timeout 300s;\n        proxy_send_timeout 300s;\n    }\n\n    location /download/ {\n        alias /home/admin/nexus-studio/download/;\n    }\n\n    location / {\n        root /home/admin/nexus-studio/;\n        try_files $uri $uri/ /main-index.html;\n    }\n}\nEOF\necho "config written"', (e3, s3) => {
          let o3 = '';
          s3.on('data', d => o3 += d); s3.on('stderr', d => o3 += d);
          s3.on('close', () => {
            console.log(o3.trim());
            
            conn.exec('nginx -t 2>&1 && nginx -s reload 2>&1 && echo "nginx reloaded"', (e4, s4) => {
              let o4 = '';
              s4.on('data', d => o4 += d); s4.on('stderr', d => o4 += d);
              s4.on('close', () => {
                console.log(o4.trim());
                
                // 验证
                conn.exec('echo "=== 验证 ===" && curl -4 -s -o /dev/null -w "root -> %{http_code}\\n" http://127.0.0.1/ && curl -4 -s -o /dev/null -w "studio -> %{http_code}\\n" http://127.0.0.1/studio/ && ls -la /home/admin/nexus-studio/', (e5, s5) => {
                  let o5 = '';
                  s5.on('data', d => o5 += d); s5.on('stderr', d => o5 += d);
                  s5.on('close', () => { console.log(o5.trim()); sftp.end(); conn.end(); });
                });
              });
            });
          });
        });
      });
    });
  });
});
conn.on('error', e => { console.error('❌', e.message); process.exit(1); });
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
