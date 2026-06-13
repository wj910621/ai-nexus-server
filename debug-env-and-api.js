const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== .env 内容 ====="`,
  `cat /home/admin/ai-nexus/.env | head -30`,
  `echo "===== 模型总数 ====="`,
  `curl -s http://localhost:3001/api/models | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{const j=JSON.parse(d);console.log('模型总数:',j.count)}catch(e){console.log('parse error')}})"`,
  `echo "===== 检查 /api/chat 测试 ====="`,
  `curl -s -X POST http://localhost:3001/api/chat -H "Content-Type: application/json" -d '{"model":"gpt4o","messages":[{"role":"user","content":"hi"}]}' 2>&1 | head -200`,
  `echo "===== 检查主站 header 区 ====="`,
  `grep -A 50 'top-bar\|header\|nav' /home/admin/nexus-studio/main-index.html | head -50`,
  `echo "===== PM2 最终状态 ====="`,
  `pm2 list 2>&1 | head -5`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
