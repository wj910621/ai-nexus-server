/* ========================================
   上传 TriGenClaw 桌面端安装包到服务器
   并更新下载页面
   ======================================== */
const { Client } = require('ssh2');
const path = require('path');
const fs = require('fs');

const HOST = '120.79.17.184';
const USER = 'admin';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;
const KEY_FILE = 'C:\\Users\\WBS—JCNC\\.ssh\\id_ed25519';
const INSTALLER = path.join(__dirname, 'trigenclaw-build', 'release', 'TriGenClaw-1.0.0-win-Setup.exe');
const REMOTE_DIR = '/home/admin/ai-nexus';

if (!fs.existsSync(INSTALLER)) {
  console.error('错误: 找不到安装包文件:', INSTALLER);
  process.exit(1);
}

console.log('安装包大小:', (fs.statSync(INSTALLER).size / 1024 / 1024).toFixed(1), 'MB');

const conn = new Client();

conn.on('ready', () => {
  console.log('已连接到', HOST);

  // 创建 download 目录
  conn.exec('mkdir -p ' + REMOTE_DIR + '/download', (err) => {
    if (err) console.log('mkdir 警告:', err.message);

    conn.sftp((err, sftp) => {
      if (err) { console.error('SFTP 错误:', err); conn.end(); return; }

      // 上传安装包
      const remoteFile = REMOTE_DIR + '/download/TriGenClaw-1.0.0-win-Setup.exe';
      const readStream = fs.createReadStream(INSTALLER);
      const writeStream = sftp.createWriteStream(remoteFile);

      writeStream.on('close', () => {
        console.log('安装包上传完成:', remoteFile);

        // 获取文件权限
        conn.exec('chmod 644 ' + remoteFile, (err) => {
          if (err) console.log('chmod 警告:', err.message);
        });

        // 检查服务器上的下载页面
        conn.exec('ls -la ' + REMOTE_DIR + '/download/', (err, stream) => {
          if (err) { console.error('ls 错误:', err); conn.end(); return; }
          let output = '';
          stream.on('data', (d) => output += d.toString());
          stream.stderr.on('data', (d) => output += d.toString());
          stream.on('close', () => {
            console.log('下载目录内容:\n' + output);

            // 检查 index.html 中的下载链接
            conn.exec('grep -n "download" ' + REMOTE_DIR + '/index.html | head -20', (err, stream) => {
              if (err) { console.log('grep 错误:', err); conn.end(); return; }
              let grepOut = '';
              stream.on('data', (d) => grepOut += d.toString());
              stream.stderr.on('data', (d) => grepOut += d.toString());
              stream.on('close', () => {
                console.log('当前下载链接:\n' + grepOut);
                console.log('\n✅ 安装包上传完成!');
                console.log('请确保网站中下载链接指向: /download/TriGenClaw-1.0.0-win-Setup.exe');
                conn.end();
              });
            });
          });
        });
      });

      writeStream.on('error', (err) => {
        console.error('上传错误:', err.message);
        conn.end();
      });

      // 显示进度
      let uploadedBytes = 0;
      readStream.on('data', (chunk) => {
        uploadedBytes += chunk.length;
        const percent = (uploadedBytes / fs.statSync(INSTALLER).size * 100).toFixed(1);
        process.stdout.write('\r上传进度: ' + percent + '% (' + (uploadedBytes / 1024 / 1024).toFixed(1) + 'MB)');
      });

      readStream.pipe(writeStream);
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
  readyTimeout: 30000,
  password: PASS,
  tryKeyboard: true,
  // Explicitly don't use key
  privateKey: undefined,
  publicKey: undefined,
};

// Remove the KEY_FILE and PASS lines at the top since we don't need them
// KEY_FILE is not used

conn.connect(connectConfig);
