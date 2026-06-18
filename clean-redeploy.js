const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;
const REMOTE_DIR = '/home/admin/ai-nexus';
const STUDIO_DIR = '/home/admin/nexus-studio';
const NVM = 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";';

conn.on('ready', () => {
  console.log('已连接，开始重新部署...');

  // Step 1: 停止服务并清理旧目录
  conn.exec(NVM + ' pm2 delete nexus-hub 2>/dev/null; pkill -f "node server.js" 2>/dev/null; rm -rf ' + STUDIO_DIR + '; mkdir -p ' + STUDIO_DIR + ' ' + REMOTE_DIR + '/logs; echo "cleaned"', (err, stream) => {
    if (err) { console.log('clean error:', err); conn.end(); return; }
    stream.on('data', d => process.stdout.write(d));
    stream.on('close', () => {
      console.log('旧文件已清理');

      // Step 2: 上传后端文件
      conn.sftp((err, sftp) => {
        if (err) { console.error('sftp error:', err); conn.end(); return; }
        
        let pending = 0;
        
        const backendFiles = {
          'server.js': path.join(__dirname, 'server.js'),
          'package.json': path.join(__dirname, 'package.json'),
        };

        for (const [name, local] of Object.entries(backendFiles)) {
          pending++;
          const remote = path.posix.join(REMOTE_DIR, name);
          sftp.fastPut(local, remote, (err) => {
            if (err) console.error(name, 'upload error:', err.message);
            else console.log('上传:', name);
            pending--;
            if (pending === 0) uploadFrontend();
          });
        }

        function uploadFrontend() {
          // 上传前端文件
          const frontendFiles = fs.readdirSync(path.join(__dirname, 'nexus-studio'));
          pending = 0;
          for (const f of frontendFiles) {
            const local = path.join(__dirname, 'nexus-studio', f);
            const stat = fs.statSync(local);
            if (stat.isFile()) {
              pending++;
              const remote = path.posix.join(STUDIO_DIR, f);
              sftp.fastPut(local, remote, (err) => {
                if (err) console.error(f, 'error:', err.message);
                else console.log('上传:', f);
                pending--;
                if (pending === 0) afterUpload();
              });
            }
          }
          if (pending === 0) afterUpload();
        }

        function afterUpload() {
          console.log('\n所有文件上传完成');

          // Step 3: 安装依赖
          conn.exec(NVM + ' cd ' + REMOTE_DIR + ' && rm -rf node_modules package-lock.json && npm install 2>&1 | tail -5', (err, stream) => {
            if (err) { console.log('npm error:', err); conn.end(); return; }
            stream.on('data', d => process.stdout.write(d));
            stream.on('close', () => {
              console.log('\nnpm install 完成');

              // Step 4: 启动服务
              conn.exec(NVM + ' cd ' + REMOTE_DIR + ' && PORT=3001 pm2 start server.js --name nexus-hub --interpreter /root/.nvm/versions/node/v18.20.8/bin/node 2>&1', (err, stream) => {
                if (err) { console.log('start error:', err); conn.end(); return; }
                stream.on('data', d => process.stdout.write(d));
                stream.on('close', () => {
                  console.log('\nPM2 启动完成');

                  // Step 5: 验证
                  setTimeout(() => {
                    conn.exec(NVM + ' pm2 list 2>&1; echo "==API=="; curl -s http://localhost:3001/api/status 2>&1 | head -5', (err, stream) => {
                      stream.on('data', d => process.stdout.write(d));
                      stream.on('close', () => {
                        console.log('\n✅ 重新部署完成！');
                        conn.end();
                      });
                    });
                  }, 3000);
                });
              });
            });
          });
        }
      });
    });
  });
}).on('error', (err) => {
  console.error('连接错误:', err.message);
}).connect({ host: HOST, port: 22, username: USER, password: PASS });
