const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接，安装 Node.js 18...');

  // 使用 nvm 安装脚本（最可靠的方式）
  conn.exec('curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh 2>/dev/null | bash 2>&1 | tail -5', (err, stream) => {
    if (err) { console.log('curl error:', err); conn.end(); return; }
    stream.on('data', d => process.stdout.write(d));
    stream.stderr.on('data', d => process.stdout.write(d));
    stream.on('close', () => {
      console.log('\nnvm install done');

      // 加载 nvm 并安装 Node 18
      conn.exec('export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; nvm install 18; nvm use 18; node -v', (err, stream) => {
        if (err) { console.log('nvm install node error:', err); conn.end(); return; }
        stream.on('data', d => process.stdout.write(d));
        stream.stderr.on('data', d => process.stdout.write(d));
        stream.on('close', () => {
          console.log('\nNode 18 install done');
          conn.end();
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
