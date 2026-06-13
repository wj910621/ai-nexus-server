const { Client } = require('ssh2');
const conn = new Client();

// 读取已修改的本地 index.html
conn.on('ready', () => {
  console.log('✅ 连接成功，开始部署...');
  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP err:', err); process.exit(1); }
    
    // 上传主站 index.html
    sftp.fastPut('G:/大模型聚合网站/index.html', '/home/admin/nexus-studio/main-index.html', (err) => {
      if (err) { console.error('Upload error:', err); process.exit(1); }
      console.log('✅ main-index.html 上传完成');
      
      // 也上传新版的 /studio/ index.html
      sftp.fastPut('G:/大模型聚合网站/index.html', '/home/admin/nexus-studio/index.html', (err2) => {
        if (err2) console.error('index.html upload skipped:', err2.message);
        else console.log('✅ index.html 上传完成');
        
        // 验证并重载 Nginx
        conn.exec('echo "验证:" && head -5 /home/admin/nexus-studio/main-index.html && echo "..." && grep "adminLogin" /home/admin/nexus-studio/main-index.html | head -1 && echo "验证通过" && nginx -t 2>&1 && nginx -s reload 2>&1', (e, s) => {
          let o = '';
          s.on('data', d => o += d); s.on('stderr', d => o += d);
          s.on('close', () => { console.log(o); sftp.end(); conn.end(); });
        });
      });
    });
  });
});
conn.on('error', e => { console.error('❌', e.message); process.exit(1); });
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
