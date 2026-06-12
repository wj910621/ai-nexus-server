const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = process.env.DEPLOY_HOST || '120.79.17.184';
const USER = process.env.DEPLOY_USER || 'admin';
const PASS = process.env.DEPLOY_PASS || '';
const KEY_FILE = process.env.DEPLOY_KEY || '';
const REMOTE_DIR = '/home/admin/ai-nexus';
const STUDIO_DIR = process.env.STUDIO_DIR || path.join(__dirname, 'nexus-studio');
const REMOTE_STUDIO_DIR = '/home/admin/nexus-studio';

if (!PASS && !KEY_FILE) {
  console.error('错误: 请设置环境变量 DEPLOY_PASS 或 DEPLOY_KEY');
  console.error('   set DEPLOY_PASS=你的密码');
  console.error('   或使用 SSH 密钥: set DEPLOY_KEY=C:\\path\\to\\id_rsa');
  process.exit(1);
}

const files = [
  path.join(__dirname, 'index.html'),
  path.join(__dirname, 'dashboard.html'),
  path.join(__dirname, 'landing.html'),
  path.join(__dirname, 'server.js'),
  path.join(__dirname, 'package.json'),
];

conn.on('ready', () => {
  console.log('已连接到 ' + HOST);
  
  conn.exec('mkdir -p ' + REMOTE_DIR, (err) => {
    if (err) { console.log('mkdir warning:', err.message); }
    
    conn.sftp((err, sftp) => {
      if (err) { console.error('SFTP 错误:', err); conn.end(); return; }

      // 递归上传目录
      function uploadDirectory(localDir, remoteDir, cb) {
        if (!fs.existsSync(localDir)) { return cb(); }
        conn.exec('mkdir -p ' + remoteDir, (err) => {
          if (err) { console.log('mkdir warning:', err.message); }
          const items = fs.readdirSync(localDir);
          let pending = items.length;
          if (pending === 0) return cb();
          items.forEach(item => {
            const localPath = path.join(localDir, item);
            const remotePath = path.posix.join(remoteDir, item);
            const stat = fs.statSync(localPath);
            if (stat.isDirectory()) {
              uploadDirectory(localPath, remotePath, () => {
                pending--;
                if (pending === 0) cb();
              });
            } else {
              const readStream = fs.createReadStream(localPath);
              const writeStream = sftp.createWriteStream(remotePath);
              writeStream.on('close', () => {
                console.log('已上传:', remotePath);
                pending--;
                if (pending === 0) cb();
              });
              readStream.pipe(writeStream);
            }
          });
        });
      }

      let uploaded = 0;
      const existingFiles = files.filter(f => fs.existsSync(f));

      if (existingFiles.length === 0) {
        return uploadStudio();
      }

      existingFiles.forEach(file => {
        const remoteFile = path.join(REMOTE_DIR, path.basename(file));
        const readStream = fs.createReadStream(file);
        const writeStream = sftp.createWriteStream(remoteFile);

        writeStream.on('close', () => {
          uploaded++;
          console.log('已上传:', path.basename(file), '(' + (fs.statSync(file).size / 1024).toFixed(1) + 'KB)');
          if (uploaded >= existingFiles.length) {
            uploadStudio();
          }
        });

        readStream.pipe(writeStream);
      });

      function uploadStudio() {
        console.log('\n上传前端 PWA 文件到 ' + REMOTE_STUDIO_DIR + '...');
        uploadDirectory(STUDIO_DIR, REMOTE_STUDIO_DIR, () => {
          console.log('\n文件上传完成，安装依赖...');
          conn.exec('cd ' + REMOTE_DIR + ' && npm install 2>&1 && echo "依赖安装完成"', (err, stream) => {
            if (err) { console.log('npm install 错误:', err); conn.end(); return; }
            stream.on('data', d => console.log(d.toString()));
            stream.stderr.on('data', d => console.log(d.toString()));
            stream.on('close', () => {
              console.log('\n启动服务器...');
              conn.exec('cd ' + REMOTE_DIR + ' && pgrep -f "node server.js" && pkill -f "node server.js"; nohup node server.js > /tmp/ai-nexus.log 2>&1 & sleep 2 && curl -s http://localhost:3001/api/status', (err, stream) => {
                if (err) { console.log('启动错误:', err); conn.end(); return; }
                stream.on('data', d => console.log(d.toString()));
                stream.stderr.on('data', d => console.log(d.toString()));
                stream.on('close', () => {
                  console.log('\n========================================');
                  console.log('  部署完成!');
                  console.log('  http://' + HOST + ':3001');
                  console.log('  前端: http://' + HOST + ':3001/studio');
                  console.log('========================================');
                  conn.end();
                });
              });
            });
          });
        });
      }
    });
  });
});

conn.on('error', (err) => {
  console.error('连接错误:', err.message);
});

const connectConfig = {
  host: HOST,
  port: 22,
  username: USER,
  readyTimeout: 10000,
};

if (KEY_FILE && fs.existsSync(KEY_FILE)) {
  connectConfig.privateKey = fs.readFileSync(KEY_FILE);
} else {
  connectConfig.password = PASS;
}

conn.connect(connectConfig);