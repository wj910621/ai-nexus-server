const { Client } = require('ssh2');
const conn = new Client();
const cmds = [
  `echo "===== API Key 配置 ====="`,
  `grep -c "DMXAPI\|OPENAI_API_KEY" /home/admin/ai-nexus/.env`,
  `grep "ADMIN" /home/admin/ai-nexus/server.js | head -5`,
  `echo "===== 检查 API 模型端点 ====="`,
  `curl -s http://localhost:3001/api/models 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'模型总数: {d[\"count\"]}')" 2>&1`,
  `curl -s http://localhost:3001/api/status 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Providers: {len(d.get(\"providers\",{}))}'); [print(f'  {k}: {len(v.get(\"models\",[]))} models') for k,v in d.get('providers',{}).items()]" 2>&1`,
  `echo "===== 检查管理入口 ====="`,
  `grep -i "admin\|管理" /home/admin/nexus-studio/main-index.html | grep -i "login\|入口\|登录" | head -5`,
  `echo "===== 查看 index.html 中是否有 admin 路由 ====="`,
  `grep -c "admin" /home/admin/nexus-studio/main-index.html`,
  `echo "===== 检查主站 header ====="`,
  `grep "top-logo\|top-links\|user-menu\|auth" /home/admin/nexus-studio/main-index.html | head -10`,
];
conn.on('ready', () => { console.log('OK'); run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= cmds.length) { console.log('Done'); conn.end(); return; }
  conn.exec(cmds[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: '120.79.17.184', port: 22, username: 'root', password: 'Wangjie910621' });
