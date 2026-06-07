const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const HOST = '120.79.17.184';
const PASS = process.env.DEPLOY_PASS || '';

const filesToUpload = [
  path.join(__dirname, 'dashboard.html'),
  path.join(__dirname, 'landing.html'),
  path.join(__dirname, 'server.js'),
  path.join(__dirname, 'package.json'),
];

function tryConnect(username) {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    let timedOut = false;
    
    const timer = setTimeout(() => {
      timedOut = true;
      conn.end();
      resolve(false);
    }, 10000);
    
    conn.on('ready', () => {
      clearTimeout(timer);
      conn.end();
      console.log(`✅ User '${username}' auth succeeded`);
      resolve(true);
    });
    
    conn.on('error', (err) => {
      if (timedOut) return;
      clearTimeout(timer);
      conn.end();
      console.log(`❌ User '${username}' error: ${err.message}`);
      resolve(false);
    });
    
    conn.on('keyboard-interactive', (name, instructions, instructionsLang, prompts, finish) => {
      if (prompts.length > 0) {
        finish([PASS]);
      } else {
        finish([]);
      }
    });
    
    conn.connect({
      host: HOST,
      port: 22,
      username: username,
      password: PASS,
      tryKeyboard: true,
      readyTimeout: 10000,
    });
  });
}

async function main() {
  console.log('🔌 尝试SSH连接...\n');
  
  const users = ['admin', 'root', 'ubuntu', 'ec2-user', 'user', 'deploy'];
  
  for (const user of users) {
    process.stdout.write(`尝试用户: ${user}... `);
    const ok = await tryConnect(user);
    if (ok) {
      console.log(`\n🎉 找到可用用户: ${user}`);
      return;
    }
  }
  
  console.log('\n❌ 所有用户均认证失败');
  console.log('请确认SSH密码是否正确，或密码登录是否已开启');
}

main().catch(console.error);
