const { Client } = require('ssh2');
const fs = require('fs');
const conn = new Client();
const HOST = '120.79.17.184'; const USER = 'root'; const PASS = 'Wangjie910621';

const indexHtml = fs.readFileSync('G:/大模型聚合网站/index.html', 'base64');
const dashboardHtml = fs.readFileSync('G:/大模型聚合网站/dashboard.html', 'base64');

conn.on('ready', () => {
  console.log('✅ Connected');
  conn.exec(`echo ${indexHtml} | base64 -d > /home/admin/nexus-studio/index.html && echo "index done"`, (e, s) => {
    let o = '';
    s.on('data', d => o += d);
    s.on('stderr', d => o += d);
    s.on('close', () => {
      if (o.trim()) console.log(o.trim());
      
      conn.exec(`echo ${dashboardHtml} | base64 -d > /home/admin/ai-nexus/dashboard.html && echo "dashboard done"`, (e2, s2) => {
        let o2 = '';
        s2.on('data', d => o2 += d);
        s2.on('stderr', d => o2 += d);
        s2.on('close', () => {
          if (o2.trim()) console.log(o2.trim());
          
          // 验证
          conn.exec('echo "=== 验证 ===" && head -5 /home/admin/nexus-studio/index.html && ls -la /home/admin/nexus-studio/index.html /home/admin/ai-nexus/dashboard.html', (e3, s3) => {
            let o3 = '';
            s3.on('data', d => o3 += d);
            s3.on('stderr', d => o3 += d);
            s3.on('close', () => { console.log(o3); conn.end(); });
          });
        });
      });
    });
  });
});
conn.on('error', e => { console.error('❌', e.message); process.exit(1); });
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
