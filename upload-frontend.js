const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';
const LOCAL_DIR = path.join(__dirname, 'nexus-studio');
const REMOTE_DIR = '/home/admin/nexus-studio';

conn.on('ready', () => {
  console.log('已连接，上传前端文件...');

  function uploadDir(localDir, remoteDir) {
    const items = fs.readdirSync(localDir);
    for (const item of items) {
      const localPath = path.join(localDir, item);
      const remotePath = path.posix.join(remoteDir, item);
      const stat = fs.statSync(localPath);
      if (stat.isDirectory()) {
        conn.exec('mkdir -p ' + remotePath, () => {});
      }
    }
  }

  conn.sftp((err, sftp) => {
    if (err) { console.error('SFTP error:', err); conn.end(); return; }

    let pending = 0;

    function uploadFile(localPath, remotePath) {
      pending++;
      sftp.fastPut(localPath, remotePath, (err) => {
        if (err) console.error('上传失败:', remotePath, err.message);
        else console.log('已上传:', remotePath);
        pending--;
        if (pending === 0) {
          console.log('\n✅ 前端文件全部上传完成');
          conn.end();
        }
      });
    }

    function walkDir(localDir, remoteDir) {
      const items = fs.readdirSync(localDir);
      for (const item of items) {
        const localPath = path.join(localDir, item);
        const remotePath = path.posix.join(remoteDir, item);
        const stat = fs.statSync(localPath);
        if (stat.isDirectory()) {
          conn.exec('mkdir -p ' + remotePath, () => {});
          walkDir(localPath, remotePath);
        } else {
          uploadFile(localPath, remotePath);
        }
      }
    }

    walkDir(LOCAL_DIR, REMOTE_DIR);
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
