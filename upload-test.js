const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
conn.on('ready', () => {
  conn.sftp((err, sftp) => {
    if (err) { console.error(err); return; }
    sftp.fastPut('G:/大模型聚合网站/nexus-studio/test-ui.html', '/home/admin/nexus-studio/test-ui.html', (err) => {
      if (err) console.error('❌', err.message);
      else console.log('✅ test-ui.html 已上传');
      sftp.end();
      conn.end();
    });
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: 'Wangjie910621'
});
