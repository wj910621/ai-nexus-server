const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const HOST = '120.79.17.184';
const USER = 'root'; // or 'admin'?
const PASS = process.env.DEPLOY_PASS || '';
const REMOTE_DIR = '/home/admin/';

const filesToUpload = [
  path.join(__dirname, 'dashboard.html'),
  path.join(__dirname, 'landing.html'),
  path.join(__dirname, 'server.js'),
  path.join(__dirname, 'package.json'),
];

const conn = new Client();

conn.on('ready', () => {
  console.log('✅ 已连接到 ' + HOST);

  // First, find the actual project directory
  conn.exec('ls -la /home/admin/', (err, stream) => {
    if (err) { console.error('ls error:', err.message); conn.end(); return; }
    let output = '';
    stream.on('data', d => output += d.toString());
    stream.stderr.on('data', d => output += d.toString());
    stream.on('close', () => {
      console.log('📁 /home/admin/ content:');
      console.log(output);

      // Determine project dir - check common patterns
      const checkDirs = ['/home/admin/', '/home/admin/ai-nexus/'];
      checkProjectDir(0);
      
      function checkProjectDir(idx) {
        if (idx >= checkDirs.length) {
          console.log('❌ 未找到项目目录，请手动确认');
          conn.end();
          return;
        }
        const dir = checkDirs[idx];
        conn.exec(`ls ${dir}server.js`, (err, stream) => {
          let out = '';
          stream.on('data', d => out += d.toString());
          stream.stderr.on('data', d => out += d.toString());
          stream.on('close', () => {
            if (out.includes('server.js')) {
              console.log(`📂 项目目录: ${dir}`);
              uploadFiles(dir);
            } else {
              checkProjectDir(idx + 1);
            }
          });
        });
      }
      
      function uploadFiles(projectDir) {
        // Upload all files via SFTP
        conn.sftp((err, sftp) => {
          if (err) { console.error('❌ SFTP error:', err.message); conn.end(); return; }
          
          let total = filesToUpload.length;
          let done = 0;
          
          filesToUpload.forEach(file => {
            if (!fs.existsSync(file)) {
              console.log(`⏭️ 跳过（不存在）: ${path.basename(file)}`);
              done++;
              checkDone();
              return;
            }
            
            const remoteFile = path.join(projectDir, path.basename(file));
            const sizeKB = (fs.statSync(file).size / 1024).toFixed(1);
            
            sftp.fastPut(file, remoteFile, (err) => {
              if (err) {
                console.error(`❌ 上传失败 ${path.basename(file)}: ${err.message}`);
              } else {
                console.log(`📤 已上传: ${path.basename(file)} (${sizeKB}KB)`);
              }
              done++;
              checkDone();
            });
          });
          
          function checkDone() {
            if (done < total) return;
            console.log('\n📦 文件上传完成！');
            runDeployCommands(projectDir);
          }
        });
      }
      
      function runDeployCommands(projectDir) {
        conn.exec(`cd ${projectDir} && npm install express cors dotenv jsonwebtoken node-fetch@2 sql.js 2>&1 || true`, (err, stream) => {
          if (err) { console.error('npm install error:', err.message); }
          let out = '';
          stream.on('data', d => out += d.toString());
          stream.stderr.on('data', d => out += d.toString());
          stream.on('close', () => {
            console.log('\n📦 依赖安装输出:', out.substring(0, 500));
            
            conn.exec('pm2 restart ai-nexus 2>&1 || pm2 start /home/admin/server.js --name ai-nexus 2>&1', (err, stream) => {
              if (err) { console.error('pm2 restart error:', err.message); }
              let pm2out = '';
              stream.on('data', d => pm2out += d.toString());
              stream.stderr.on('data', d => pm2out += d.toString());
              stream.on('close', () => {
                console.log('\n🔄 PM2 重启输出:', pm2out);
                
                // Verify
                setTimeout(() => {
                  conn.exec('curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/', (err, stream) => {
                    let httpCode = '';
                    stream.on('data', d => httpCode += d.toString());
                    stream.on('close', () => {
                      console.log(`\n🌐 服务状态: HTTP ${httpCode}`);
                      console.log('========================================');
                      console.log('  ✅ 部署完成!');
                      console.log('  https://j3trisheng.com/dashboard');
                      console.log('========================================');
                      conn.end();
                    });
                  });
                }, 2000);
              });
            });
          });
        });
      }
    });
  });
});

conn.on('keyboard-interactive', (name, instructions, instructionsLang, prompts, finish) => {
  console.log('🔑 Keyboard-interactive auth requested');
  if (prompts.length > 0) {
    finish([PASS]);
  } else {
    finish([]);
  }
});

conn.connect({
  host: HOST,
  port: 22,
  username: 'admin',
  password: PASS,
  tryKeyboard: true,
  readyTimeout: 15000,
  algorithms: {
    kex: ['diffie-hellman-group14-sha256', 'diffie-hellman-group14-sha1', 'diffie-hellman-group-exchange-sha256'],
    cipher: ['aes256-ctr', 'aes192-ctr', 'aes128-ctr', 'aes256-gcm@openssh.com', 'aes128-gcm@openssh.com'],
    hmac: ['hmac-sha2-256', 'hmac-sha2-512', 'hmac-sha1'],
  },
});

console.log('🔌 正在连接 ' + HOST + '...');
