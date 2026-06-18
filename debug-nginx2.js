const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const { DEPLOY_PASS } = require('./deploy-config');
const PASS = DEPLOY_PASS;

const commands = [
  // Verbose curl
  `echo "===== Verbose: j3trisheng.com/ ====="`,
  `curl -v -H "Host: j3trisheng.com" http://localhost/ 2>&1 | head -20`,
  `echo "===== Verbose: j3trisheng.com/studio/ ====="`,
  `curl -v -H "Host: j3trisheng.com" http://localhost/studio/ 2>&1 | head -20`,
  `echo "===== Verbose: nothing ====="`,
  `curl -v http://localhost/studio/ 2>&1 | head -20`,
  `echo "===== Test index.html directly ====="`,
  `cat /home/admin/nexus-studio/index.html | head -5`,
  `echo "===== Test permissions ====="`,
  `ls -la /home/admin/nexus-studio/`,
  `sudo -u nginx cat /home/admin/nexus-studio/index.html > /dev/null 2>&1 && echo "nginx CAN read" || echo "nginx CANNOT read"`,
];

const conn = new Client();
conn.on('ready', () => { runCommands(0); });
conn.on('error', (err) => { console.error('❌:', err.message); process.exit(1); });
function runCommands(idx) {
  if (idx >= commands.length) { conn.end(); return; }
  conn.exec(commands[idx], (err, stream) => {
    if (err) { console.log(`[ERR]: ${err.message}`); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => { if (out.trim()) console.log(out.trim()); runCommands(idx + 1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
