const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
conn.on('ready', () => {
  conn.sftp((err, sftp) => {
    if (err) { console.error(err); return; }
    
    // 下载新版本 ui.js 并检查
    sftp.fastGet('/home/admin/nexus-studio/js/ui.js', 'd:/temp_ui_downloaded.js', (err) => {
      if (err) { console.error('Download failed:', err); return; }
      console.log('Downloaded OK');
      
      // 在 Node.js 中验证语法
      const content = fs.readFileSync('d:/temp_ui_downloaded.js', 'utf8');
      
      // 检查是否有 BOM
      console.log('First 3 bytes hex:', content.charCodeAt(0).toString(16), content.charCodeAt(1).toString(16), content.charCodeAt(2).toString(16));
      
      // 执行 IIFE 并捕获异常
      try {
        // Simulate browser environment minimally  
        const result = eval(content);
        console.log('IIFE result type:', typeof result);
        if (result) console.log('init type:', typeof result.init);
      } catch(e) {
        console.log('ERROR during IIFE execution:', e.message);
        console.log('Stack:', e.stack?.split('\n').slice(0,3).join('\n'));
      }
      
      sftp.end();
      conn.end();
      fs.unlinkSync('d:/temp_ui_downloaded.js');
    });
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: CHANGE_ME
});
