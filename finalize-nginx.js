const { Client } = require('ssh2');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

conn.on('ready', () => {
  console.log('已连接，清理旧 Nginx 配置...');

  // 禁用其他可能冲突的配置文件
  conn.exec('cd /etc/nginx/conf.d && mv ai-nexus.conf ai-nexus.conf.disabled 2>/dev/null; mv j3trisheng.conf.bak j3trisheng.conf.bak.disabled 2>/dev/null; mv j3trisheng-v2.conf j3trisheng-v2.conf.disabled 2>/dev/null; echo "cleaned"', (err, stream) => {
    stream.on('data', d => process.stdout.write(d));
    stream.on('close', () => {

      // 测试并重载
      conn.exec('nginx -t 2>&1', (err, stream) => {
        stream.on('data', d => process.stdout.write(d));
        stream.on('close', () => {
          conn.exec('nginx -s reload 2>&1', (err, stream) => {
            stream.on('data', d => process.stdout.write(d));
            stream.on('close', () => {
              console.log('\n✅ Nginx 配置已清理并重载');
              conn.end();
            });
          });
        });
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
