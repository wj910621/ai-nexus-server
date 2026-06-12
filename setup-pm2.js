const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';
const REMOTE_DIR = '/home/admin/ai-nexus';
const NVM = 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";';

conn.on('ready', () => {
  console.log('已连接，直接配置 PM2...');

  // 先杀掉所有 node 进程（除了 PM2 自己）
  conn.exec('pkill -f "node server.js" 2>/dev/null; sleep 2; echo "killed old processes"', (err, stream) => {
    stream.on('data', d => process.stdout.write(d));
    stream.on('close', () => {

      // 用 nvm 的 node 直接 pm2 start（不使用 ecosystem config）
      conn.exec(NVM + ' cd ' + REMOTE_DIR + ' && pm2 delete all 2>/dev/null; PORT=3001 pm2 start server.js --name nexus-hub --interpreter /root/.nvm/versions/node/v18.20.8/bin/node 2>&1', (err, stream) => {
        if (err) { console.log('pm2 error:', err); conn.end(); return; }
        stream.on('data', d => process.stdout.write(d));
        stream.on('close', () => {
          console.log('\npm2 start 完成');

          // 检查状态
          setTimeout(() => {
            conn.exec(NVM + ' pm2 list 2>&1; echo "==="; curl -s http://localhost:3001/api/status 2>&1 | head -3', (err, stream) => {
              stream.on('data', d => process.stdout.write(d));
              stream.on('close', () => {
                console.log('\n');

                // 保存 PM2 并配置开机自启
                conn.exec(NVM + ' pm2 save 2>&1', (err, stream) => {
                  stream.on('data', d => process.stdout.write(d));
                  stream.on('close', () => {
                    console.log('PM2 saved');

                    conn.exec(NVM + ' pm2 startup systemd -u root --hp /root 2>&1 | tail -5', (err, stream) => {
                      stream.on('data', d => process.stdout.write(d));
                      stream.on('close', () => {
                        console.log('\n✅ PM2 配置完成！');
                        conn.end();
                      });
                    });
                  });
                });
              });
            });
          }, 3000);
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
