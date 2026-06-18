const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

conn.on('ready', () => {
  console.log('已连接，重启 PM2 服务...');
  
  conn.exec('pm2 restart nexus-hub', (err, stream) => {
    if (err) {
      console.error('PM2 restart error:', err.message);
      // 尝试通过 node 路径重启
      conn.exec('source /root/.nvm/nvm.sh 2>/dev/null; nvm use 18 2>/dev/null; pm2 restart nexus-hub', (err2, stream2) => {
        if (err2) console.error('NVM restart also failed:', err2.message);
        else {
          stream2.on('data', d => process.stdout.write(d.toString()));
          stream2.on('close', () => { console.log('\n✅ PM2 重启完成'); conn.end(); });
        }
      });
      return;
    }
    stream.on('data', d => process.stdout.write(d.toString()));
    stream.on('close', () => { console.log('\n✅ PM2 重启完成'); conn.end(); });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
