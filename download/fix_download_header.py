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
        if out: print(out[:300])
    return out, err

# Fix the Content-Disposition filename
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
    }

    # .exe 文件强制下载
    location ~* \\.exe$ {
        root /home/admin/nexus-studio/download/;
        add_header Content-Disposition 'attachment';
        add_header X-Content-Type-Options 'nosniff';
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

print("=== Updating SSL config ===")
stdin, stdout, stderr = ssh.exec_command("cat > /etc/nginx/conf.d/j3trisheng-ssl.conf")
stdin.write(ssl_config)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()

# Also update HTTP
http_config = """
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name j3trisheng.com www.j3trisheng.com _;
    root /home/admin/nexus-studio/;
    index landing.html;
    location = / { try_files /landing.html =404; }
    location = /studio { return 301 /studio/; }
    location /studio/ { alias /home/admin/nexus-studio/; index index.html; try_files $uri $uri/ /index.html; }
    location = /download { return 301 /download/; }
    location /download/ { alias /home/admin/nexus-studio/download/; index index.html; try_files $uri $uri/ =404; autoindex off; }
    location ~* \\.exe$ { root /home/admin/nexus-studio/download/; add_header Content-Disposition 'attachment'; add_header X-Content-Type-Options 'nosniff'; }
    location /api/ { proxy_pass http://127.0.0.1:3001; proxy_set_header Host $host; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_read_timeout 300s; proxy_connect_timeout 5s; proxy_buffer_size 128k; proxy_buffers 4 256k; proxy_busy_buffers_size 256k; }
    location /v1/ { proxy_pass http://127.0.0.1:3001; proxy_set_header Host $host; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_read_timeout 300s; proxy_connect_timeout 5s; proxy_buffer_size 128k; proxy_buffers 4 256k; proxy_busy_buffers_size 256k; }
    location / { try_files $uri $uri/ /landing.html; }
}
"""
print("=== Updating HTTP config ===")
stdin, stdout, stderr = ssh.exec_command("cat > /etc/nginx/conf.d/j3trisheng.conf")
stdin.write(http_config)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()

run("nginx -t 2>&1", "Test nginx")
run("nginx -s reload 2>&1", "Reload nginx")
run("curl -s -I https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe 2>&1 | grep -iE 'content-disposition|HTTP/'", "Verify header")

print("\n=== DONE ===")
ssh.close()
