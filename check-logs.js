const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  // 检查 PM2 错误日志
  conn.exec('tail -50 /root/.pm2/logs/nexus-hub-error.log', (err, stream) => {
    let output = '';
    stream.on('data', d => output += d.toString());
    stream.on('close', () => {
      console.log('=== PM2 Error Log (last 50 lines) ===');
      console.log(output);
      conn.end();
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
