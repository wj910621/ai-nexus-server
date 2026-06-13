const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
conn.on('ready', () => {
  console.log('连接成功，上传新前端...');

  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP error:', err); conn.end(); return; }

    const files = [
      { local: 'G:/大模型聚合网站/new-nexus/index.html', remote: '/home/admin/nexus-studio/index.html' },
    ];

    let pending = files.length;
    for (const f of files) {
      sftp.fastPut(f.local, f.remote, (err) => {
        if (err) console.error('❌', path.basename(f.local), err.message);
        else console.log('✅', path.basename(f.local));
        pending--;
        if (pending === 0) {
          console.log('\n🎉 新前端上传完成！');
          console.log('请访问: http://120.79.17.184:3001/studio/');
          sftp.end();
          conn.end();
        }
      });
    }
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: 'Wangjie910621'
});
