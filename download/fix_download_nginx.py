import paramiko

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!")

def run(cmd, desc=""):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if desc:
        print(f"\n=== {desc} ===")
        if out: print(out[:500])
        if err: print(f"ERR: {err[:200]}")
    return out, err

# Fix 1: Add Content-Disposition header for .exe downloads in nginx SSL config
ssl_config = """
server {
    listen 443 ssl http2;
    server_name j3trisheng.com www.j3trisheng.com;

    ssl_certificate /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root /home/admin/nexus-studio/;
    index landing.html;

    location / {
        try_files /landing.html =404;
    }

    location = /studio { return 301 /studio/; }

    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        try_files $uri $uri/ /index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # 下载目录
    location = /download { return 301 /download/; }

    location /download/ {
        alias /home/admin/nexus-studio/download/;
        index index.html;
        try_files $uri $uri/ =404;
        autoindex off;
        # 强制 .exe 文件弹出下载对话框
        location ~* \\.exe$ {
            add_header Content-Disposition 'attachment; filename="$1"';
            add_header X-Content-Type-Options 'nosniff';
        }
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_connect_timeout 5s;
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
        proxy_connect_timeout 5s;
    }
}
"""

print("\n=== Fix 1: Updating nginx SSL config with Content-Disposition ===")
stdin, stdout, stderr = ssh.exec_command("cat > /etc/nginx/conf.d/j3trisheng-ssl.conf")
stdin.write(ssl_config)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()
print("SSL config updated!")

# Also update HTTP config
http_config = """
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name j3trisheng.com www.j3trisheng.com _;

    root /home/admin/nexus-studio/;
    index landing.html;

    location = / { try_files /landing.html =404; }

    location = /studio { return 301 /studio/; }
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location = /download { return 301 /download/; }
    location /download/ {
        alias /home/admin/nexus-studio/download/;
        index index.html;
        try_files $uri $uri/ =404;
        autoindex off;
        location ~* \\.exe$ {
            add_header Content-Disposition 'attachment; filename="$1"';
            add_header X-Content-Type-Options 'nosniff';
        }
    }

    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_connect_timeout 5s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_connect_timeout 5s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    location / { try_files $uri $uri/ /landing.html; }
}
"""
print("\n=== Updating HTTP config ===")
stdin, stdout, stderr = ssh.exec_command("cat > /etc/nginx/conf.d/j3trisheng.conf")
stdin.write(http_config)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()
print("HTTP config updated!")

# Test and reload
run("nginx -t 2>&1", "Test nginx config")
run("nginx -s reload 2>&1", "Reload nginx")

# Test download headers
run("curl -s -I https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe 2>&1 | grep -E 'HTTP|content-disposition|content-type'", "Verify download headers")

# Test Cloudflare cache purge by adding a version query param
run("curl -s -I 'https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe?v=2' 2>&1 | grep -E 'HTTP|cf-cache|content-disposition'", "Check fresh download cache")

print("\n=== ALL FIXES APPLIED ===")
ssh.close()
