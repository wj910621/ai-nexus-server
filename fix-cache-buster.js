const { Client } = require('ssh2');
const conn = new Client();

conn.on('ready', () => {
  // 修改 index.html，给 ui.js 加缓存破坏参数
  const sedCmd = "sed -i 's|src=\"js/ui.js\"|src=\"js/ui.js?v=20260613\"|' /home/admin/nexus-studio/index.html && echo 'Updated index.html'";
  
  conn.exec(sedCmd, (err, stream) => {
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('close', () => {
      console.log(out);
      
      // 验证
      conn.exec("grep 'ui.js' /home/admin/nexus-studio/index.html", (err2, stream2) => {
        stream2.on('data', d => process.stdout.write(d.toString()));
        stream2.on('close', () => conn.end());
      });
    });
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: 'Wangjie910621'
});
