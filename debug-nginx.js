const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const commands = [
  `cat /etc/nginx/conf.d/j3trisheng.conf`,
  `echo "=== active config ==="`,
  `nginx -T 2>&1 | grep -A 10 "server_name j3trisheng"`,
  `echo "=== listen directives ==="`,
  `nginx -T 2>&1 | grep "listen "`,
  `echo "=== nginx test ==="`,
  `nginx -t 2>&1`,
];

const conn = new Client();
conn.on('ready', () => {
  runCommands(0);
});
conn.on('error', (err) => { console.error('❌:', err.message); process.exit(1); });
function runCommands(idx) {
  if (idx >= commands.length) { conn.end(); return; }
  conn.exec(commands[idx], (err, stream) => {
    if (err) { console.log(`[ERR]: ${err.message}`); runCommands(idx + 1); return; }
    let out = '';
    stream.on('data', d => out += d.toString());
    stream.on('stderr', d => out += d.toString());
    stream.on('close', () => { console.log(out.trim()); runCommands(idx + 1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
