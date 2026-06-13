const { Client } = require('ssh2');
const fs = require('fs');
const conn = new Client();
const HOST = '120.79.17.184'; const USER = 'root'; const PASS = 'Wangjie910621';

// 读取本地更新后的文件
const indexHtml = fs.readFileSync('G:/大模型聚合网站/index.html');
const dashboardHtml = fs.readFileSync('G:/大模型聚合网站/dashboard.html');

conn.on('ready', () => {
  console.log('✅ SSH 连接成功，开始部署...');
  
  // 写入 index.html
  conn.exec('cat > /home/admin/nexus-studio/index.html', (err, stream) => {
    if (err) { console.error('ERR:', err); process.exit(1); }
    stream.stdin.end(indexHtml);
    stream.on('close', () => {
      console.log('✅ index.html 已部署');
      
      // 写入 dashboard.html
      conn.exec('cat > /home/admin/ai-nexus/dashboard.html', (err, s2) => {
        if (err) { console.error('ERR:', err); process.exit(1); }
        s2.stdin.end(dashboardHtml);
        s2.on('close', () => {
          console.log('✅ dashboard.html 已部署');
          
          // 验证
          conn.exec('ls -la /home/admin/nexus-studio/index.html /home/admin/ai-nexus/dashboard.html 2>&1; echo "=== 验证 ==="; head -5 /home/admin/nexus-studio/index.html', (e, s3) => {
            let o = '';
            s3.on('data', d => o += d);
            s3.on('stderr', d => o += d);
            s3.on('close', () => { console.log(o); conn.end(); });
          });
        });
      });
    });
  });
});
conn.on('error', e => { console.error('❌', e.message); process.exit(1); });
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
