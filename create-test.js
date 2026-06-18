const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

conn.on('ready', () => {
  // 创建一个最小测试 HTML，只加载 ui.js
  const testHtml = '<!DOCTYPE html><html><body><h1>Test</h1><script src="js/ui.js"></script><script>console.log("NexusUI:", typeof NexusUI); console.log("init:", typeof NexusUI?.init); if(typeof NexusUI?.init==="function"){document.body.innerHTML+="<p style=color:green>init OK</p>"}else{document.body.innerHTML+="<p style=color:red>init FAILED: "+(typeof NexusUI)+"</p>"}</script></body></html>';

  conn.exec('cat > /home/admin/nexus-studio/test.html << "ENDOFFILE"\n' + testHtml + '\nENDOFFILE', (err, stream) => {
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('close', () => {
      console.log(out);
      conn.end();
    });
  });
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
