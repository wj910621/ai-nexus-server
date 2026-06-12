const { Client } = require('ssh2');
const fs = require('fs');

const conn = new Client();
conn.on('ready', () => {
  conn.sftp((err, sftp) => {
    if (err) { console.error(err); return; }
    
    const files = [
      { local: 'D:/OneDrive/文档/Nexus AI Studio 2/nexus-ai-studio/js/ui.js', remote: '/home/admin/nexus-studio/js/ui.js' },
      { local: 'G:/大模型聚合网站/nexus-studio/test-ui-v2.html', remote: '/home/admin/nexus-studio/test-ui-v2.html' },
    ];
    
    let pending = files.length;
    for (const f of files) {
      sftp.fastPut(f.local, f.remote, (err) => {
        if (err) console.error('❌', f.local.split('/').pop(), err.message);
        else console.log('✅', f.local.split('/').pop());
        pending--;
        if (pending === 0) { sftp.end(); conn.end(); }
      });
    }
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: 'Wangjie910621'
});
