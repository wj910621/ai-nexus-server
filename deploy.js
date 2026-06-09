const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = process.env.DEPLOY_HOST || '120.79.17.184';
const USER = process.env.DEPLOY_USER || 'admin';
const PASS = process.env.DEPLOY_PASS || '';
const KEY_FILE = process.env.DEPLOY_KEY || '';
const REMOTE_DIR = '/home/admin/ai-nexus';

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
      
      let uploaded = 0;
      files.forEach(file => {
        if (!fs.existsSync(file)) {
          console.log('跳过（不存在）:', file);
          return;
        }
        
        const remoteFile = path.join(REMOTE_DIR, path.basename(file));
        const readStream = fs.createReadStream(file);
        const writeStream = sftp.createWriteStream(remoteFile);
        
        writeStream.on('close', () => {
          uploaded++;
          console.log('已上传:', path.basename(file), '(' + (fs.statSync(file).size / 1024).toFixed(1) + 'KB)');
          
          if (uploaded >= files.filter(f => fs.existsSync(f)).length) {
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
                    console.log('========================================');
                    conn.end();
                  });
                });
              });
            });
          }
        });
        
        readStream.pipe(writeStream);
      });
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