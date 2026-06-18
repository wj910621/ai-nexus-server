const { Client } = require('ssh2');
const conn = new Client();
conn.on('ready', () => {
  // 给 ui.js 添加时间戳版本，强制浏览器加载新版本
  conn.exec('cd /home/admin/nexus-studio/js && cp ui.js ui.js.bak && echo "/* v20260613-0255 */" > ui.js.new && cat ui.js >> ui.js.new && mv ui.js.new ui.js && echo "Updated with version stamp"', (err, stream) => {
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('close', () => {
      console.log(out);
      conn.end();
    });
  });
}).connect({
  host: '120.79.17.184', port: 22,
  username: 'root', password: CHANGE_ME
});
