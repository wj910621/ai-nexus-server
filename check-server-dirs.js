const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  let cmd = '';
  
  // 1. 查看所有可能的前端目录
  cmd += 'echo "=== 所有 nexus-studio 目录 ==="; ';
  cmd += 'ls -la /home/admin/nexus-studio/ 2>/dev/null; ';
  cmd += 'echo; echo "=== JS 目录 ==="; ';
  cmd += 'ls -la /home/admin/nexus-studio/js/ 2>/dev/null; ';
  cmd += 'echo; echo "=== ui.js 大小 ==="; ';
  cmd += 'wc -c /home/admin/nexus-studio/js/ui.js 2>/dev/null; ';
  cmd += 'echo; echo "=== server.js 中的 STUDIO_DIR ==="; ';
  cmd += 'grep "STUDIO_DIR" /home/admin/ai-nexus/server.js; ';
  cmd += 'echo; echo "=== 端口 3001 的进程 ==="; ';
  cmd += 'lsof -i:3001 2>/dev/null || ss -tlnp | grep 3001; ';
  cmd += 'echo; echo "=== 检查是否有其他 node 进程运行 ==="; ';
  cmd += 'ps aux | grep "node.*server" | grep -v grep; ';
  
  conn.exec(cmd, (err, stream) => {
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('close', () => {
      console.log(out);
      conn.end();
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
