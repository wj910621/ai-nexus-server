const { Client } = require('ssh2');
const fs = require('fs');
const conn = new Client();
const HOST = '120.79.17.184'; const USER = 'root'; const PASS = 'Wangjie910621';

// 使用流式传输 - 通过 sftp
conn.on('ready', () => {
  console.log('✅ Connected, starting SFTP...');
  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP error:', err); process.exit(1); }
    
    const localIndex = 'G:/大模型聚合网站/index.html';
    const remoteIndex = '/home/admin/nexus-studio/index.html';
    const localDash = 'G:/大模型聚合网站/dashboard.html';
    const remoteDash = '/home/admin/ai-nexus/dashboard.html';
    
    // 先上传 index.html
    sftp.fastPut(localIndex, remoteIndex, (err) => {
      if (err) { console.error('Upload index error:', err); process.exit(1); }
      console.log('✅ index.html 上传完成');
      
      // 上传 dashboard.html
      sftp.fastPut(localDash, remoteDash, (err) => {
        if (err) { console.error('Upload dash error:', err); process.exit(1); }
        console.log('✅ dashboard.html 上传完成');
        
        // 验证
        conn.exec('head -5 /home/admin/nexus-studio/index.html && echo "---" && ls -la /home/admin/nexus-studio/index.html /home/admin/ai-nexus/dashboard.html', (e, s) => {
          let o = '';
          s.on('data', d => o += d);
          s.on('stderr', d => o += d);
          s.on('close', () => { console.log(o); sftp.end(); conn.end(); });
        });
      });
    });
  });
});
conn.on('error', e => { console.error('❌', e.message); process.exit(1); });
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
