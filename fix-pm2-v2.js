const { Client } = require('ssh2');
const c = new Client();
c.on('ready', () => {
  c.exec('pm2 delete nexus-hub 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; sleep 1; cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1 | tail -5; pm2 save 2>&1; pm2 list 2>&1', (e, s) => {
    let o = '';
    s.on('data', d => o += d);
    s.on('stderr', d => o += d);
    s.on('close', () => { console.log(o); c.end(); });
  });
});
c.on('error', e => { console.error('ERR:', e.message); process.exit(1); });
c.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
