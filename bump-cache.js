const { Client } = require('ssh2');
const conn = new Client();
conn.on('ready', () => {
  conn.exec("sed -i 's|ui.js?v=20260613b|ui.js?v=20260613c|' /home/admin/nexus-studio/index.html && echo 'Done'", (err, stream) => {
    stream.on('data', d => process.stdout.write(d.toString()));
    stream.on('close', () => conn.end());
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: 'Wangjie910621'
});
