const { Client } = require('ssh2');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;
const LOCAL_DIR = path.join(__dirname, 'nexus-studio');
const REMOTE_DIR = '/home/admin/nexus-studio';

conn.on('ready', () => {
  console.log('已连接，上传前端...');

  // 只上传关键文件
  conn.sftp((err, sftp) => {
    if (err) { conn.end(); return; }
    let pending = 2;

    sftp.fastPut(path.join(LOCAL_DIR, 'index.html'), path.posix.join(REMOTE_DIR, 'index.html'), (err) => {
      if (err) console.log('index upload error:', err.message);
      else console.log('index.html 已上传');
      pending--;
      if (pending === 0) done();
    });

    sftp.fastPut(path.join(LOCAL_DIR, 'sw.js'), path.posix.join(REMOTE_DIR, 'sw.js'), (err) => {
      if (err) console.log('sw upload error:', err.message);
      else console.log('sw.js 已上传');
      pending--;
      if (pending === 0) done();
    });

    function done() {
      console.log('\n✅ 前端上传完成');
      conn.end();
    }
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
