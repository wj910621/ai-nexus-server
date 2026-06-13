const { Client } = require('ssh2');
const HOST = '120.79.17.184';
const USER = 'root';
const PASS = 'Wangjie910621';

const config = `server {
    listen 80;
    listen [::]:80;
    server_name j3trisheng.com www.j3trisheng.com;

    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
    }

    location /download/ {
        alias /home/admin/nexus-studio/download/;
    }

    location = / {
        return 302 /studio/;
    }

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
    }
}
`;

const commands = [
  `cat > /etc/nginx/conf.d/j3trisheng.conf << 'EOF'\n${config}\nEOF`,
  `echo "写入完成"`,
  `nginx -t 2>&1`,
  `nginx -s reload 2>&1`,
  `curl -4 -s -o /dev/null -w "v4:studio -> %{http_code}\\n" -H "Host: j3trisheng.com" http://127.0.0.1/studio/`,
  `curl -6 -s -o /dev/null -w "v6:studio -> %{http_code}\\n" -H "Host: j3trisheng.com" http://[::1]/studio/`,
  `curl -s -o /dev/null -w "v6:root -> %{http_code}\\n" -H "Host: j3trisheng.com" http://localhost/`,
];

const conn = new Client();
conn.on('ready', () => { run(0); });
conn.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });
function run(i) {
  if (i >= commands.length) { conn.end(); return; }
  conn.exec(commands[i], (e, s) => {
    if (e) { console.log('ERR:', e.message); run(i+1); return; }
    let o = '';
    s.on('data', d => o += d.toString());
    s.on('stderr', d => o += d.toString());
    s.on('close', () => { if (o.trim()) console.log(o.trim()); run(i+1); });
  });
}
conn.connect({ host: HOST, port: 22, username: USER, password: PASS });
