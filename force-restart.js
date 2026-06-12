const { Client } = require('ssh2');
const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接服务器，执行强制修复...\n');

  // 1. 杀掉占用 3001 端口的进程
  conn.exec('fuser -k 3001/tcp 2>/dev/null; sleep 1; echo "端口已释放"', (err, stream) => {
    stream.on('data', d => process.stdout.write(d.toString()));
    stream.on('close', () => {

      // 2. 运行 pm2 update 同步版本
      conn.exec('source /root/.nvm/nvm.sh 2>/dev/null; nvm use 18 2>/dev/null; pm2 update 2>&1', (err2, stream2) => {
        stream2.on('data', d => process.stdout.write(d.toString()));
        stream2.on('close', () => {

          // 3. 重启 nexus-hub
          conn.exec('source /root/.nvm/nvm.sh 2>/dev/null; nvm use 18 2>/dev/null; pm2 restart nexus-hub 2>&1', (err3, stream3) => {
            stream3.on('data', d => process.stdout.write(d.toString()));
            stream3.on('close', () => {

              // 4. 验证服务状态
              setTimeout(() => {
                conn.exec('curl -s http://localhost:3001/api/status | head -c 200', (err4, stream4) => {
                  let out = '';
                  stream4.on('data', d => out += d.toString());
                  stream4.on('close', () => {
                    console.log('\n=== API 状态检查 ===');
                    console.log(out);
                    conn.end();
                  });
                });
              }, 2000);
            });
          });
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
